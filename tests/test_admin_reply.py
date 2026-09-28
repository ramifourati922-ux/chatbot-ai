# tests/test_admin_reply.py
"""
Historique complet et réponse du conseiller depuis /admin.

Les fonctions d'envoi WhatsApp / Messenger sont TOUJOURS remplacées par
un enregistreur local : aucun test ne contacte Meta. Le client web est
simulé par une fausse connexion WebSocket enregistrée dans le
ConnectionManager. Conversations créées par le vrai handle_message avec
des messages sans LLM (demande d'humain) : seul PostgreSQL est requis.
"""

import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, text

from app.api.routes import messenger, websocket, whatsapp
from app.config import settings
from app.db import database
from app.main import app
from app.models import User
from app.services.dialogue_manager import handle_message, wait_for_pending_persistence

EXPLICIT = "Je veux parler à un agent humain"


@pytest_asyncio.fixture
async def prefix():
    await database.engine.dispose(close=False)
    try:
        async with database.AsyncSessionLocal() as db:
            await db.execute(text("select 1"))
    except Exception as e:
        pytest.skip(f"PostgreSQL indisponible : {e}")
    p = f"test-reply-{uuid.uuid4().hex[:8]}-"
    yield p
    await wait_for_pending_persistence()
    async with database.AsyncSessionLocal() as db:
        await db.execute(delete(User).where(
            User.external_id.like(f"{p}%") | User.external_id.like(f"web:{p}%")))
        await db.commit()
    await database.engine.dispose(close=False)


@pytest.fixture
def sent(monkeypatch):
    """Enregistreur à la place des envois Meta, avec des identifiants
    factices (jamais utilisés : la fonction d'envoi est remplacée)."""
    calls = []

    async def record_whatsapp(to, body):
        calls.append(("whatsapp", to, body))

    async def record_messenger(psid, body):
        calls.append(("messenger", psid, body))

    monkeypatch.setattr(whatsapp, "_send_whatsapp_message", record_whatsapp)
    monkeypatch.setattr(messenger, "_send_messenger_message", record_messenger)
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "jeton-factice")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "id-factice")
    monkeypatch.setattr(settings, "MESSENGER_PAGE_ACCESS_TOKEN", "jeton-factice")
    return calls


@pytest_asyncio.fixture
async def client(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_USERNAME", "conseiller-test")
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", "mot-de-passe-test")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
        auth=("conseiller-test", "mot-de-passe-test"),
    ) as c:
        yield c


async def _escalate(session_id, channel):
    """Crée une conversation escaladée et renvoie son identifiant."""
    await handle_message("bonjour", session_id=session_id, channel=channel)
    await handle_message(EXPLICIT, session_id=session_id, channel=channel)
    await wait_for_pending_persistence()
    async with database.AsyncSessionLocal() as db:
        return (await db.execute(text(
            "select c.id from conversations c join users u on u.id = c.user_id where u.external_id = :e"
        ), {"e": session_id})).scalar_one()


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send_json(self, payload):
        self.sent.append(payload)


# ── Historique ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_history_is_complete_and_chronological(prefix, client):
    conv_id = await _escalate(f"{prefix}wa", "whatsapp")
    response = await client.get(f"/admin/escalations/{conv_id}/messages")
    assert response.status_code == 200
    body = response.json()
    assert body["customer_id"] == f"{prefix}wa"
    assert body["channel"] == "whatsapp"
    assert body["status"] == "escalated"
    assert [(m["role"], m["content"]) for m in body["messages"]][::2] == [("user", "bonjour"), ("user", EXPLICIT)]
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user", "assistant"]
    times = [m["created_at"] for m in body["messages"]]
    assert times == sorted(times)


@pytest.mark.asyncio
async def test_history_of_unknown_conversation_is_404(prefix, client):
    assert (await client.get(f"/admin/escalations/{uuid.uuid4()}/messages")).status_code == 404


# ── Réponse WhatsApp / Messenger ────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("channel", ["whatsapp", "messenger"])
async def test_reply_is_sent_on_the_original_channel_and_stored(prefix, client, sent, channel):
    conv_id = await _escalate(f"{prefix}{channel}", channel)
    response = await client.post(f"/admin/escalations/{conv_id}/reply", json={"text": "  Bonjour, je m'en occupe.  "})
    assert response.status_code == 200
    assert response.json()["channel"] == channel
    assert sent == [(channel, f"{prefix}{channel}", "Bonjour, je m'en occupe.")]

    history = (await client.get(f"/admin/escalations/{conv_id}/messages")).json()["messages"]
    assert (history[-1]["role"], history[-1]["content"]) == ("agent", "Bonjour, je m'en occupe.")


@pytest.mark.asyncio
async def test_reply_without_meta_credentials_is_409_not_a_fake_success(prefix, client, sent, monkeypatch):
    """Sans identifiants, les fonctions d'envoi SIMULENT l'envoi sans erreur :
    la route doit le détecter et le dire au conseiller."""
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", None)
    conv_id = await _escalate(f"{prefix}wa", "whatsapp")
    response = await client.post(f"/admin/escalations/{conv_id}/reply", json={"text": "Bonjour"})
    assert response.status_code == 409
    assert "identifiants Meta" in response.json()["detail"]
    assert sent == []
    history = (await client.get(f"/admin/escalations/{conv_id}/messages")).json()["messages"]
    assert "agent" not in [m["role"] for m in history]


@pytest.mark.asyncio
async def test_send_failure_is_502_and_nothing_is_stored(prefix, client, sent, monkeypatch):
    async def failing(to, body):
        raise RuntimeError("Meta indisponible")

    monkeypatch.setattr(whatsapp, "_send_whatsapp_message", failing)
    conv_id = await _escalate(f"{prefix}wa", "whatsapp")
    response = await client.post(f"/admin/escalations/{conv_id}/reply", json={"text": "Bonjour"})
    assert response.status_code == 502
    history = (await client.get(f"/admin/escalations/{conv_id}/messages")).json()["messages"]
    assert "agent" not in [m["role"] for m in history]


# ── Réponse web (WebSocket) ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reply_reaches_a_connected_web_client(prefix, client, sent, monkeypatch):
    client_id = f"{prefix}web"
    conv_id = await _escalate(f"web:{client_id}", "web")  # identifiant tel que l'enregistre /ws
    fake = FakeWebSocket()
    monkeypatch.setitem(websocket.manager._connections, client_id, fake)

    response = await client.post(f"/admin/escalations/{conv_id}/reply", json={"text": "Bonjour"})
    assert response.status_code == 200
    assert response.json()["channel"] == "web"
    assert fake.sent == [{"response": "Bonjour", "from_agent": True, "escalated": False, "intent": "agent"}]
    assert sent == []


@pytest.mark.asyncio
async def test_reply_to_a_disconnected_web_client_is_409(prefix, client, sent):
    conv_id = await _escalate(f"web:{prefix}gone", "web")
    response = await client.post(f"/admin/escalations/{conv_id}/reply", json={"text": "Bonjour"})
    assert response.status_code == 409
    assert "injoignable" in response.json()["detail"]
    history = (await client.get(f"/admin/escalations/{conv_id}/messages")).json()["messages"]
    assert "agent" not in [m["role"] for m in history]


@pytest.mark.asyncio
async def test_web_conversation_declared_as_whatsapp_is_never_sent_on_whatsapp(prefix, client, sent):
    """POST /chat/ accepte channel="whatsapp" : l'identifiant web: prime,
    sinon le message partirait sur WhatsApp vers un faux numéro."""
    conv_id = await _escalate(f"web:{prefix}21600000099", "whatsapp")
    history = (await client.get(f"/admin/escalations/{conv_id}/messages")).json()
    assert history["channel"] == "web"
    response = await client.post(f"/admin/escalations/{conv_id}/reply", json={"text": "Bonjour"})
    assert response.status_code == 409  # client web non connecté
    assert sent == []


# ── Validation ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_blank_reply_is_rejected(prefix, client, sent):
    conv_id = await _escalate(f"{prefix}wa", "whatsapp")
    assert (await client.post(f"/admin/escalations/{conv_id}/reply", json={"text": "   "})).status_code == 422
    assert (await client.post(f"/admin/escalations/{conv_id}/reply", json={"text": ""})).status_code == 422
    assert sent == []


@pytest.mark.asyncio
async def test_reply_to_unknown_conversation_is_404(prefix, client, sent):
    response = await client.post(f"/admin/escalations/{uuid.uuid4()}/reply", json={"text": "Bonjour"})
    assert response.status_code == 404
    assert sent == []
