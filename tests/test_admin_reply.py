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


# ── Prise en main : le bot se tait tant que le conseiller a la main ─────

from app.services import dialogue_manager  # noqa: E402

AGENT_TEXT = "Bonjour, ici le service client, je m'occupe de vous."


async def _take_over(client, prefix, channel="whatsapp"):
    """Escalade + réponse du conseiller : renvoie (session, conversation)."""
    session_id = f"{prefix}{channel}"
    conv_id = await _escalate(session_id, channel)
    response = await client.post(f"/admin/escalations/{conv_id}/reply", json={"text": AGENT_TEXT})
    assert response.status_code == 200
    return session_id, conv_id


async def _history(client, conv_id):
    return (await client.get(f"/admin/escalations/{conv_id}/messages")).json()


@pytest.mark.asyncio
async def test_reply_takes_over_the_conversation(prefix, client, sent):
    session_id, conv_id = await _take_over(client, prefix)
    assert (await _history(client, conv_id))["status"] == "agent"
    assert await dialogue_manager.agent_has_the_conversation(session_id, "whatsapp") is True


@pytest.mark.asyncio
async def test_bot_is_silent_while_the_agent_has_the_conversation(prefix, client, sent):
    session_id, conv_id = await _take_over(client, prefix)
    result = await handle_message("Merci, et le délai de livraison ?", session_id=session_id, channel="whatsapp")
    await wait_for_pending_persistence()
    assert result.handled_by_agent is True
    assert result.response == ""
    # Message du client enregistré, aucune réponse du bot après celle du conseiller
    roles = [(m["role"], m["content"]) for m in (await _history(client, conv_id))["messages"]]
    assert roles[-2:] == [("agent", AGENT_TEXT), ("user", "Merci, et le délai de livraison ?")]


@pytest.mark.asyncio
async def test_whatsapp_webhook_sends_nothing_during_takeover(prefix, client, sent, monkeypatch):
    session_id, conv_id = await _take_over(client, prefix)
    sent.clear()
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", None)  # signature non exigée dans ce test
    payload = {"entry": [{"changes": [{"value": {"messages": [
        {"from": session_id, "type": "text", "text": {"body": "vous êtes là ?"}}]}}]}]}
    assert (await client.post("/webhook/whatsapp", json=payload)).status_code == 200
    await wait_for_pending_persistence()
    assert sent == []  # ni réponse du bot ni accusé de réception
    assert (await _history(client, conv_id))["messages"][-1]["content"] == "vous êtes là ?"


@pytest.mark.asyncio
async def test_web_client_gets_an_empty_handled_by_agent_answer(prefix, client, sent):
    """POST /chat/ : réponse vide marquée handled_by_agent (rien à afficher)."""
    web_id = f"{prefix}site"
    conv_id = await _escalate(f"web:{web_id}", "web")
    async with database.AsyncSessionLocal() as db:  # prise en main (client web non connecté ici)
        from app.db.repositories.conversation_repository import ConversationRepository
        from datetime import datetime, timezone
        repo = ConversationRepository(db)
        conv = await repo.get_by_id(conv_id)
        now = datetime.now(timezone.utc)
        await repo.add_message(conv_id, "agent", AGENT_TEXT, {}, created_at=now)
        await repo.take_over(conv, "conseiller-test", now)
        await db.commit()
    response = await client.post("/chat/", json={"message": "d'accord", "session_id": web_id})
    await wait_for_pending_persistence()
    assert response.status_code == 200
    assert response.json()["handled_by_agent"] is True
    assert response.json()["response"] == ""


@pytest.mark.asyncio
async def test_taken_over_conversation_stays_listed_with_the_latest_customer_message(prefix, client, sent):
    session_id, conv_id = await _take_over(client, prefix)
    await handle_message("Merci, et le délai de livraison ?", session_id=session_id, channel="whatsapp")
    await wait_for_pending_persistence()
    [item] = [e for e in (await client.get("/admin/escalations")).json() if e["conversation_id"] == str(conv_id)]
    assert item["status"] == "agent"
    assert item["last_question"] == "Merci, et le délai de livraison ?"
    assert item["reason"] == "explicit"


@pytest.mark.asyncio
async def test_bot_resumes_after_resolve(prefix, client, sent):
    session_id, conv_id = await _take_over(client, prefix)
    assert (await client.post(f"/admin/escalations/{conv_id}/resolve")).status_code == 200
    result = await handle_message("bonjour", session_id=session_id, channel="whatsapp")
    await wait_for_pending_persistence()
    assert result.handled_by_agent is False
    assert result.response  # réponse de politesse du bot


@pytest.mark.asyncio
async def test_bot_resumes_after_one_hour_without_agent_message(prefix, client, sent):
    session_id, conv_id = await _take_over(client, prefix)
    async with database.AsyncSessionLocal() as db:  # dernier message du conseiller il y a 61 min
        await db.execute(text(
            "update messages set created_at = created_at - interval '61 minutes' "
            "where conversation_id = :c and role = 'agent'"), {"c": conv_id})
        await db.commit()
    result = await handle_message("bonjour", session_id=session_id, channel="whatsapp")
    await wait_for_pending_persistence()
    assert result.handled_by_agent is False
    assert result.response
    # Toujours visible sur /admin, en attente : le conseiller ne l'a pas close
    assert (await _history(client, conv_id))["status"] == "escalated"


@pytest.mark.asyncio
async def test_takeover_only_concerns_that_customer(prefix, client, sent):
    await _take_over(client, prefix)
    result = await handle_message("bonjour", session_id=f"{prefix}other", channel="whatsapp")
    await wait_for_pending_persistence()
    assert result.handled_by_agent is False


@pytest.mark.asyncio
async def test_agent_reply_is_added_to_the_bot_memory(prefix, client, sent):
    session_id, _ = await _take_over(client, prefix)
    session = await dialogue_manager._session_manager.get_session(session_id)
    assert session["messages"][-1]["content"] == AGENT_TEXT
    assert session["messages"][-1]["role"] == "assistant"
    await dialogue_manager._session_manager.delete_session(session_id)


@pytest.mark.asyncio
async def test_bot_answers_if_postgres_is_unavailable(monkeypatch):
    def broken_session():
        raise RuntimeError("PostgreSQL indisponible")

    monkeypatch.setattr(dialogue_manager, "AsyncSessionLocal", broken_session)
    assert await dialogue_manager.agent_has_the_conversation("216xxxxxxxx", "whatsapp") is False
