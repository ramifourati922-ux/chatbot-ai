# tests/test_websocket_security.py
"""
Sécurité de /ws/{client_id} : l'en-tête Origin doit appartenir à la
liste CORS (settings.cors_origins), sinon la connexion est fermée avec le
code 1008 sans qu'aucun message ne soit traité. handle_message est
remplacé par un bouchon : ni Groq, ni Redis, ni PostgreSQL.
"""

from types import SimpleNamespace

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
