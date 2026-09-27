# tests/test_conversation_persistence.py
"""
Persistance des conversations dans PostgreSQL (dialogue_manager).

Nécessite PostgreSQL (docker compose), ChromaDB peuplé et une
GROQ_API_KEY : les échanges passent par le vrai handle_message.
"""

import time
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.config import settings
from app.db import database
from app.models import Conversation, Message, User
from app.services import dialogue_manager
from app.services.dialogue_manager import handle_message, wait_for_pending_persistence
from app.services.rag import vector_store


def _kb_indexed():
    try:
        return vector_store.count() > 0
    except Exception:
        return False


GROQ_KEY_MISSING = not settings.GROQ_API_KEY or settings.GROQ_API_KEY == "your_groq_api_key_here"
pytestmark = pytest.mark.skipif(
    GROQ_KEY_MISSING or not _kb_indexed(),
    reason="GROQ_API_KEY manquante ou ChromaDB non peuplé",
)


@pytest_asyncio.fixture
async def db_session_id():
    """
    Identifiant de session unique, et nettoyage de ses lignes en base.
    engine.dispose(close=False) : sous pytest-asyncio, chaque test a sa
    propre boucle asyncio, alors que les connexions asyncpg du pool sont
    liées à la boucle qui les a créées (en production il n'y a qu'une
    boucle, pas de problème). close=False abandonne ces connexions sans
    tenter de les fermer : les fermer depuis une autre boucle bloque.
    """
    await database.engine.dispose(close=False)
    session_id = f"test-persist-{uuid.uuid4()}"
    yield session_id
    await wait_for_pending_persistence()
    async with database.AsyncSessionLocal() as db:
        await db.execute(delete(User).where(User.external_id == session_id))  # cascade → conversations, messages
        await db.commit()
    await database.engine.dispose(close=False)


async def _conversations_of(session_id: str):
    async with database.AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.external_id == session_id))).scalar_one_or_none()
        if user is None:
            return None, []
        convs = (await db.execute(select(Conversation).where(Conversation.user_id == user.id))).scalars().all()
        return user, convs


async def _messages_of(conv_id):
    async with database.AsyncSessionLocal() as db:
        rows = await db.execute(
            select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at)
        )
        return rows.scalars().all()


@pytest.mark.asyncio
async def test_full_exchange_is_persisted(db_session_id):
    first = await handle_message("Avez-vous l'Arduino Uno ?", session_id=db_session_id, channel="whatsapp")
    second = await handle_message("et la garantie ?", session_id=db_session_id, channel="whatsapp")
    await wait_for_pending_persistence()

    user, convs = await _conversations_of(db_session_id)
    assert user is not None and user.channel == "whatsapp"
    assert len(convs) == 1  # les deux échanges dans la MÊME conversation
    conv = convs[0]
    assert conv.channel == "whatsapp" and conv.status == "active"

    messages = await _messages_of(conv.id)
    assert [m.role for m in messages] == ["user", "assistant", "user", "assistant"]
    assert [m.content for m in messages] == [
        "Avez-vous l'Arduino Uno ?", first.response, "et la garantie ?", second.response,
    ]
    assert messages[1].metadata_["sources"]  # sources RAG conservées
    assert messages[1].processing_time_ms == first.processing_time_ms


@pytest.mark.asyncio
async def test_messages_have_distinct_increasing_timestamps(db_session_id):
    """Régression (test manuel) : le message du client et la réponse
    partageaient le même created_at, now() PostgreSQL de la transaction ;
    l'ordre par created_at était donc arbitraire ("assistant → user").
    Deux échanges sans appel LLM (politesse, puis escalade)."""
    await handle_message("bonjour", session_id=db_session_id, channel="web")
    await handle_message("Je veux parler à un agent humain", session_id=db_session_id, channel="web")
    await wait_for_pending_persistence()

    _, convs = await _conversations_of(db_session_id)
    messages = await _messages_of(convs[0].id)  # triés par created_at
    timestamps = [m.created_at for m in messages]

    assert len(set(timestamps)) == 4  # tous différents
    assert timestamps == sorted(timestamps) and all(a < b for a, b in zip(timestamps, timestamps[1:]))
    assert [(m.role, m.content) for m in messages][::2] == [
        ("user", "bonjour"), ("user", "Je veux parler à un agent humain"),
    ]
    assert [m.role for m in messages] == ["user", "assistant", "user", "assistant"]


@pytest.mark.asyncio
async def test_escalation_is_persisted_with_escalated_status(db_session_id):
    result = await handle_message("Je veux parler à un agent humain", session_id=db_session_id, channel="web")
    assert result.escalated
    await wait_for_pending_persistence()

    _, convs = await _conversations_of(db_session_id)
    assert len(convs) == 1 and convs[0].status == "escalated"
    messages = await _messages_of(convs[0].id)
    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[1].metadata_["escalation_reason"] == "explicit"


@pytest.mark.asyncio
async def test_persistence_adds_no_latency_to_the_response(db_session_id, monkeypatch):
    """L'écriture en base est une tâche de fond : même lente (1 s simulée),
    elle ne retarde pas la réponse. Testé sur le chemin de l'escalade
    (sans appel LLM), le plus rapide et donc le plus sensible."""
    original = dialogue_manager._persist_exchange

    async def slow_persist(*args):
        await __import__("asyncio").sleep(1.0)
        await original(*args)

    monkeypatch.setattr(dialogue_manager, "_persist_exchange", slow_persist)
    t0 = time.perf_counter()
    result = await handle_message("Je veux parler à un agent humain", session_id=db_session_id, channel="web")
    elapsed = time.perf_counter() - t0

    assert result.escalated
    assert elapsed < 0.5
    await wait_for_pending_persistence()
    _, convs = await _conversations_of(db_session_id)
    assert len(convs) == 1  # écrite quand même, après coup


@pytest.mark.asyncio
async def test_postgres_failure_does_not_break_the_chat(db_session_id, monkeypatch):
    def broken_session():
        raise ConnectionError("PostgreSQL indisponible")

    monkeypatch.setattr(dialogue_manager, "AsyncSessionLocal", broken_session)
    result = await handle_message("Je veux parler à un agent humain", session_id=db_session_id, channel="web")
    await wait_for_pending_persistence()
    assert result.escalated and result.response  # le client a sa réponse malgré la panne
