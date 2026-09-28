# tests/test_websocket_security.py
"""
Sécurité des sessions web :
- /ws/{client_id} : l'en-tête Origin doit appartenir à la liste CORS
  (settings.cors_origins), sinon la connexion est fermée avec le code
  1008 sans qu'aucun message ne soit traité ;
- /ws et POST /chat/ : l'identifiant choisi par le client est préfixé
  par "web:", il ne peut plus désigner une session WhatsApp/Messenger.
handle_message est remplacé par un bouchon (ni Groq, ni Redis, ni
PostgreSQL), sauf dans le test de bout en bout, sans appel au LLM.
"""

import uuid
from types import SimpleNamespace

import httpx
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api import rate_limit
from app.api.routes import websocket as ws_route
from app.config import settings
from app.main import app

calls = []


async def _fake_handle_message(message, session_id=None, channel="web"):
    calls.append({"message": message, "session_id": session_id, "channel": channel})
    return SimpleNamespace(
        response=f"écho : {message}", session_id=session_id, intent="general", confidence=0.9,
        sources=[], processing_time_ms=1, escalated=False, escalation_reason=None,
    )


@pytest.fixture(autouse=True)
def stub(monkeypatch):
    calls.clear()
    monkeypatch.setattr(ws_route, "handle_message", _fake_handle_message)
    rate_limit.reset()
    yield
    rate_limit.reset()


def _assert_refused(headers):
    with TestClient(app).websocket_connect("/ws/test-origin", headers=headers) as ws:
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_text()
    assert closed.value.code == rate_limit.WS_POLICY_VIOLATION
    assert calls == []  # aucun message traité


# ── Origin ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("origin", ["http://localhost:8000", "http://127.0.0.1:8000"])
def test_allowed_origin_is_accepted(origin):
    assert origin in settings.cors_origins
    with TestClient(app).websocket_connect("/ws/test-origin", headers={"origin": origin}) as ws:
        ws.send_text("bonjour")
        assert ws.receive_json()["response"] == "écho : bonjour"


@pytest.mark.parametrize("origin", [
    "https://evil.test",
    "http://localhost:8000.evil.test",  # préfixe d'une origine autorisée
    "http://localhost:9999",            # même hôte, autre port
    "null",                             # page locale (file://) ou iframe isolée
])
def test_unknown_origin_is_refused(origin):
    _assert_refused({"origin": origin})


def test_missing_origin_is_refused():
    _assert_refused({})


def test_origin_list_follows_configuration(monkeypatch):
    monkeypatch.setattr(settings, "CORS_ALLOWED_ORIGINS", "https://demo.ngrok-free.app")
    with TestClient(app).websocket_connect(
        "/ws/test-origin", headers={"origin": "https://demo.ngrok-free.app"}
    ) as ws:
        ws.send_text("bonjour")
        assert ws.receive_json()["response"] == "écho : bonjour"
    # Les origines par défaut ne sont plus autorisées une fois la liste définie
    calls.clear()
    _assert_refused({"origin": "http://localhost:8000"})


def test_refused_origin_does_not_use_a_connection_slot(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_WS_CONNECTIONS", 1)
    _assert_refused({"origin": "https://evil.test"})
    _assert_refused({"origin": "https://evil.test"})
    with TestClient(app).websocket_connect(
        "/ws/test-origin", headers={"origin": settings.cors_origins[0]}
    ) as ws:
        ws.send_text("bonjour")
        assert ws.receive_json()["response"] == "écho : bonjour"


# ── Sessions web séparées des sessions WhatsApp / Messenger ─────────────
# Scénario corrigé : un client web qui choisit comme identifiant le numéro
# d'un client WhatsApp rejoignait sa session Redis (même clé), donc son
# historique, transmis au LLM.

WHATSAPP_NUMBER = "21600000099"  # fictif


def test_ws_client_id_equal_to_a_whatsapp_number_gets_a_separate_session():
    with TestClient(app).websocket_connect(
        f"/ws/{WHATSAPP_NUMBER}", headers={"origin": settings.cors_origins[0]}
    ) as ws:
        ws.send_text("bonjour")
        data = ws.receive_json()
    assert calls[0]["session_id"] == f"web:{WHATSAPP_NUMBER}"
    assert calls[0]["channel"] == "web"
    assert data["session_id"] == WHATSAPP_NUMBER  # le client voit son identifiant


@pytest.mark.asyncio
async def test_whatsapp_webhook_keeps_the_raw_number_as_session(monkeypatch):
    """Les deux espaces de noms sont disjoints : WhatsApp garde le numéro brut."""
    from app.api.routes import whatsapp as wa_route

    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", None)      # signature non exigée
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", None)    # aucun envoi réel
    monkeypatch.setattr(wa_route, "handle_message", _fake_handle_message)
    payload = {"entry": [{"changes": [{"value": {"messages": [
        {"from": WHATSAPP_NUMBER, "type": "text", "text": {"body": "bonjour"}}]}}]}]}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.post("/webhook/whatsapp", json=payload)).status_code == 200
    assert calls == [{"message": "bonjour", "session_id": WHATSAPP_NUMBER, "channel": "whatsapp"}]


@pytest.mark.asyncio
async def test_http_chat_session_id_is_namespaced_whatever_the_declared_channel(monkeypatch):
    from app.api.routes import chat as chat_route

    monkeypatch.setattr(chat_route, "handle_message", _fake_handle_message)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        # Le client prétend être sur WhatsApp : le préfixe suit le canal réel (HTTP = web)
        claimed = await c.post("/chat/", json={
            "message": "bonjour", "session_id": WHATSAPP_NUMBER, "channel": "whatsapp"})
        generated = await c.post("/chat/", json={"message": "bonjour"})
    assert calls[0]["session_id"] == f"web:{WHATSAPP_NUMBER}"
    assert claimed.json()["session_id"] == WHATSAPP_NUMBER
    # Sans identifiant : généré par la route, préfixé en interne, renvoyé sans préfixe
    assert calls[1]["session_id"] == f"web:{generated.json()['session_id']}"


@pytest.mark.asyncio
async def test_web_client_does_not_touch_the_whatsapp_history():
    """
    Bout en bout avec le vrai dialogue_manager et le vrai stockage de
    session (Redis, ou mémoire si Redis est absent). "Bonjour" = échange de
    politesse : aucun appel au LLM.
    """
    from sqlalchemy import delete

    from app.db import database
    from app.models import User
    from app.services import dialogue_manager
    from app.services.dialogue_manager import handle_message, wait_for_pending_persistence

    number = f"216{uuid.uuid4().int % 10**8:08d}"  # fictif, unique
    sessions = dialogue_manager._session_manager
    await database.engine.dispose(close=False)
    try:
        # Le client WhatsApp écrit (comme le fait le webhook)
        await handle_message(message="Bonjour", session_id=number, channel="whatsapp")
        whatsapp_before = await sessions.get_session(number)

        # Un client web utilise ce numéro comme identifiant de session
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            response = await c.post("/chat/", json={"message": "Bonjour", "session_id": number})
        assert response.status_code == 200

        whatsapp_after = await sessions.get_session(number)
        web = await sessions.get_session(f"web:{number}")
        assert whatsapp_after["messages"] == whatsapp_before["messages"]  # historique WhatsApp intact
        assert whatsapp_after["channel"] == "whatsapp"
        assert web["channel"] == "web" and len(web["messages"]) == 2      # session web distincte
    finally:
        await wait_for_pending_persistence()
        await sessions.delete_session(number)
        await sessions.delete_session(f"web:{number}")
        try:
            async with database.AsyncSessionLocal() as db:
                await db.execute(delete(User).where(User.external_id.in_([number, f"web:{number}"])))
                await db.commit()
        except Exception:
            pass  # PostgreSQL absent : rien n'a été persisté
        await database.engine.dispose(close=False)
