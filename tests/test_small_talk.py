# tests/test_small_talk.py
"""
Échanges de politesse (salutation, remerciement, au revoir) : réponse
toute prête sans RAG, au lieu d'une escalade low_rag_confidence.

Les tests du classifieur sont purs. Ceux qui passent par handle_message
n'appellent pas le LLM (politesse et escalade sont court-circuitées),
sauf le test "question précédée d'un bonjour", qui nécessite Groq et
ChromaDB.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete

from app.config import settings
from app.db import database
from app.models import User
from app.services import dialogue_manager
from app.services.dialogue_manager import SMALL_TALK_MESSAGES, handle_message, wait_for_pending_persistence
from app.services.intent_classifier import Category, IntentClassifier
from app.services.rag import vector_store

clf = IntentClassifier()

# Les 7 messages du test manuel qui déclenchaient à tort une escalade
# low_rag_confidence : (message, type attendu, langue de la réponse)
FALSE_ESCALATIONS = [
    ("hello", "greeting", "en"),
    ("bonsoir", "greeting", "fr"),
    ("bonjour", "greeting", "fr"),
    ("salut", "greeting", "fr"),
    ("merci", "thanks", "fr"),
    ("aslema", "greeting", "tn"),
    ("مرحبا", "greeting", "ar"),
]


def _kb_indexed():
    try:
        return vector_store.count() > 0
    except Exception:
        return False


GROQ_KEY_MISSING = not settings.GROQ_API_KEY or settings.GROQ_API_KEY == "your_groq_api_key_here"


# --- Classifieur ---

@pytest.mark.parametrize("message,kind,language", FALSE_ESCALATIONS + [
    ("Bonjour !", "greeting", "fr"),
    ("comment ça va ?", "greeting", "fr"),
    ("السلام عليكم", "greeting", "ar"),
    ("3aslema", "greeting", "tn"),
    ("merci beaucoup", "thanks", "fr"),
    ("thanks a lot", "thanks", "en"),
    ("شكرًا", "thanks", "ar"),
    ("choukran", "thanks", "tn"),
    ("au revoir", "goodbye", "fr"),
    ("bonne journée", "goodbye", "fr"),
    ("merci, au revoir", "thanks", "fr"),
])
def test_small_talk_detected(message, kind, language):
    result = clf.classify(message)
    assert result.category == Category.SMALL_TALK
    assert result.intent == kind
    assert result.language_hint == language
    assert result.requires_escalation is False


@pytest.mark.parametrize("message", [
    "bonjour, j'ai une question sur la garantie",  # vraie question → RAG
    "bonjour, quelle est la garantie ?",
    "merci pour l'info sur la livraison",
    "merci, c'est réglé",  # reste un signal de satisfaction, pas une politesse
    "Hello where is my order CMD123?",
    "ok",
    "good",
    "ça va",  # aucun mot avec une langue propre : trop ambigu
])
def test_message_with_content_is_not_small_talk(message):
    result = clf.classify(message)
    assert result.category != Category.SMALL_TALK


def test_explicit_escalation_still_wins():
    result = clf.classify("Bonjour, je veux parler à un agent humain")
    assert result.requires_escalation and result.escalation_reason == "explicit"


# --- Bout en bout (handle_message) ---

@pytest_asyncio.fixture
async def session_prefix():
    """Préfixe de session unique ; supprime ensuite les lignes créées en
    base par la persistance. dispose(close=False) : voir
    test_conversation_persistence (une boucle asyncio par test)."""
    await database.engine.dispose(close=False)
    prefix = f"test-smalltalk-{uuid.uuid4().hex[:8]}-"
    yield prefix
    await wait_for_pending_persistence()
    async with database.AsyncSessionLocal() as db:
        await db.execute(delete(User).where(User.external_id.like(f"{prefix}%")))
        await db.commit()
    await database.engine.dispose(close=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("message,kind,language", FALSE_ESCALATIONS)
async def test_false_escalations_now_get_a_courtesy_reply(session_prefix, message, kind, language):
    result = await handle_message(message, session_id=f"{session_prefix}{kind}", channel="web")
    assert result.escalated is False
    assert result.escalation_reason is None
    assert result.intent == kind
    assert result.language == language
    assert result.response == SMALL_TALK_MESSAGES[kind][language]
    assert result.sources == []


@pytest.mark.asyncio
async def test_thanks_resets_rag_loop_counter(session_prefix):
    session_id = f"{session_prefix}reset"
    session_manager = dialogue_manager._session_manager  # même instance que handle_message
    await session_manager.get_or_create(session_id, "web")
    await session_manager.increment_rag_attempts(session_id)
    await session_manager.increment_rag_attempts(session_id)

    await handle_message("merci", session_id=session_id, channel="web")
    assert (await session_manager.get_context(session_id))["rag_attempts_count"] == 0


@pytest.mark.asyncio
async def test_explicit_escalation_still_escalates(session_prefix):
    result = await handle_message("Je veux parler à un agent humain", session_id=f"{session_prefix}human")
    assert result.escalated is True
    assert result.escalation_reason == "explicit"


@pytest.mark.skipif(GROQ_KEY_MISSING or not _kb_indexed(), reason="GROQ_API_KEY manquante ou ChromaDB non peuplé")
@pytest.mark.asyncio
async def test_question_with_greeting_still_goes_to_rag(session_prefix):
    result = await handle_message("bonjour, j'ai une question sur la garantie", session_id=f"{session_prefix}rag")
    assert result.escalated is False
    assert result.intent == "general"
    assert "sav/garantie.txt" in result.sources
