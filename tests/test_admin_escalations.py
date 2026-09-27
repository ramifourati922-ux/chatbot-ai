# tests/test_admin_escalations.py
"""
Tableau de bord des conseillers (routes /admin) : là où une escalade
aboutit.

Les conversations sont créées par le vrai handle_message, avec des
messages qui n'appellent ni le LLM ni ChromaDB (demande d'humain,
frustration, politesse) : seul PostgreSQL est nécessaire. Chaque test
utilise ses propres identifiants de session et supprime ses données.
"""

import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, select, text

from app.config import settings
from app.db import database
from app.main import app
from app.models import Conversation, User
from app.services.dialogue_manager import handle_message, wait_for_pending_persistence

EXPLICIT = "Je veux parler à un agent humain"
FRUSTRATION = "votre service est nul"


@pytest_asyncio.fixture
async def prefix():
    """Préfixe de session unique ; saute le test si PostgreSQL est absent.
    dispose(close=False) : une boucle asyncio par test, cf.
    test_conversation_persistence."""
    await database.engine.dispose(close=False)
    try:
        async with database.AsyncSessionLocal() as db:
            await db.execute(text("select 1"))
    except Exception as e:
        pytest.skip(f"PostgreSQL indisponible : {e}")
    p = f"test-admin-{uuid.uuid4().hex[:8]}-"
    yield p
    await wait_for_pending_persistence()
    async with database.AsyncSessionLocal() as db:
        await db.execute(delete(User).where(User.external_id.like(f"{p}%")))
        await db.commit()
    await database.engine.dispose(close=False)


@pytest_asyncio.fixture
async def client(monkeypatch):
    """Client authentifié (routes /admin protégées par HTTP Basic, voir
    tests/test_admin_auth.py pour les refus)."""
    monkeypatch.setattr(settings, "ADMIN_USERNAME", "conseiller-test")
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", "mot-de-passe-test")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
        auth=("conseiller-test", "mot-de-passe-test"),
    ) as c:
        yield c


async def _talk(session_id, *messages, channel="web"):
    for m in messages:
        await handle_message(m, session_id=session_id, channel=channel)
    await wait_for_pending_persistence()


async def _mine(client, prefix):
    """Escalades listées qui appartiennent à ce test (la base peut en contenir d'autres)."""
    response = await client.get("/admin/escalations")
    assert response.status_code == 200
    return [e for e in response.json() if (e["customer_id"] or "").startswith(prefix)]


@pytest.mark.asyncio
async def test_escalation_appears_in_list(prefix, client):
    await _talk(f"{prefix}wa", "bonjour", EXPLICIT, channel="whatsapp")

    [item] = await _mine(client, prefix)
    assert item["customer_id"] == f"{prefix}wa"
    assert item["channel"] == "whatsapp"
    assert item["last_question"] == EXPLICIT  # la question qui a déclenché le transfert
    assert item["reason"] == "explicit"
    assert 0 <= item["waiting_seconds"] < 60
    uuid.UUID(item["conversation_id"])


@pytest.mark.asyncio
async def test_non_escalated_conversations_never_appear(prefix, client):
    await _talk(f"{prefix}polite", "bonjour", "merci", "au revoir")
    await _talk(f"{prefix}escalated", FRUSTRATION)

    items = await _mine(client, prefix)
    assert [i["customer_id"] for i in items] == [f"{prefix}escalated"]
    assert items[0]["reason"] == "frustration"


@pytest.mark.asyncio
async def test_most_recent_escalation_first(prefix, client):
    await _talk(f"{prefix}first", EXPLICIT)
    await _talk(f"{prefix}second", FRUSTRATION)

    items = await _mine(client, prefix)
    assert [i["customer_id"] for i in items] == [f"{prefix}second", f"{prefix}first"]


@pytest.mark.asyncio
async def test_resolve_removes_escalation_from_list(prefix, client):
    await _talk(f"{prefix}c", EXPLICIT)
    [item] = await _mine(client, prefix)

    response = await client.post(f"/admin/escalations/{item['conversation_id']}/resolve")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "resolved" and body["resolved_at"]

    assert await _mine(client, prefix) == []  # disparue de la liste
    async with database.AsyncSessionLocal() as db:
        conv = await db.get(Conversation, uuid.UUID(item["conversation_id"]))
        assert conv.status == "resolved"
        assert conv.context["resolved_at"]  # heure de résolution enregistrée


@pytest.mark.asyncio
async def test_resolve_errors(prefix, client):
    await _talk(f"{prefix}c", EXPLICIT)
    [item] = await _mine(client, prefix)
    url = f"/admin/escalations/{item['conversation_id']}/resolve"

    assert (await client.post(url)).status_code == 200
    assert (await client.post(url)).status_code == 409  # déjà traitée
    assert (await client.post(f"/admin/escalations/{uuid.uuid4()}/resolve")).status_code == 404

    # Conversation jamais escaladée : 409
    await _talk(f"{prefix}polite", "bonjour")
    async with database.AsyncSessionLocal() as db:
        polite = (await db.execute(
            select(Conversation).join(User).where(User.external_id == f"{prefix}polite")
        )).scalar_one()
    assert (await client.post(f"/admin/escalations/{polite.id}/resolve")).status_code == 409


@pytest.mark.asyncio
async def test_new_escalation_after_resolution_reappears(prefix, client):
    """Un client déjà pris en charge qui redemande un humain, dans la même
    conversation, doit réapparaître, avec la raison de la NOUVELLE escalade."""
    await _talk(f"{prefix}c", EXPLICIT)
    [item] = await _mine(client, prefix)
    await client.post(f"/admin/escalations/{item['conversation_id']}/resolve")

    await _talk(f"{prefix}c", FRUSTRATION)
    [again] = await _mine(client, prefix)
    assert again["conversation_id"] == item["conversation_id"]
    assert again["reason"] == "frustration"
    assert again["last_question"] == FRUSTRATION


@pytest.mark.asyncio
async def test_admin_page_is_served(client):
    response = await client.get("/admin")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "/admin/escalations" in response.text
