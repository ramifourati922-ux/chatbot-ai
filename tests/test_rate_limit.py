# tests/test_rate_limit.py
"""
Limitation de débit par IP : POST /chat/, /users/ (limite partagée entre
toutes ses routes) et /ws (connexions simultanées + messages).

Fenêtres réduites à 1 seconde par monkeypatch pour tester la remise à
zéro sans attendre une minute. handle_message et la base sont remplacés
par des bouchons : ni appel Groq ni PostgreSQL.
"""

import time
import uuid
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api import rate_limit
from app.api.routes import chat as chat_route
from app.api.routes import websocket as ws_route
from app.config import settings
from app.db.database import get_db
from app.db.repositories.user_repository import UserRepository
from app.main import app

LIMIT = 3
WINDOW_S = 1


async def _fake_handle_message(message, session_id=None, channel="web"):
    return SimpleNamespace(
        response=f"écho : {message}", session_id=session_id or "s", intent="general",
        confidence=0.9, sources=[], processing_time_ms=1, escalated=False, escalation_reason=None,
    )


async def _fake_db():
    yield None


async def _no_user(self, *args, **kwargs):
    return None


async def _no_users(self, *args, **kwargs):
    return []


@pytest.fixture(autouse=True)
def small_limits(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_CHAT", f"{LIMIT}/{WINDOW_S} second")
    monkeypatch.setattr(settings, "RATE_LIMIT_USERS", f"{LIMIT}/{WINDOW_S} second")
    monkeypatch.setattr(settings, "RATE_LIMIT_WS_MESSAGES", f"{LIMIT}/{WINDOW_S} second")
    monkeypatch.setattr(settings, "RATE_LIMIT_WS_CONNECTIONS", 2)
    monkeypatch.setattr(chat_route, "handle_message", _fake_handle_message)
    monkeypatch.setattr(ws_route, "handle_message", _fake_handle_message)
    monkeypatch.setattr(UserRepository, "get_by_id", _no_user)
    monkeypatch.setattr(UserRepository, "update", _no_user)
    monkeypatch.setattr(UserRepository, "list_all", _no_users)
    app.dependency_overrides[get_db] = _fake_db
    rate_limit.reset()
    yield
    app.dependency_overrides.pop(get_db, None)
    rate_limit.reset()


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _wait_for_new_window():
    time.sleep(WINDOW_S + 0.2)


# ── POST /chat/ ─────────────────────────────────────────────────────────

async def _chat(client):
    return await client.post("/chat/", json={"message": "bonjour", "channel": "web"})


@pytest.mark.asyncio
async def test_chat_under_limit_passes(client):
    for _ in range(LIMIT):
        response = await _chat(client)
        assert response.status_code == 200
        assert response.json()["response"] == "écho : bonjour"


@pytest.mark.asyncio
async def test_chat_over_limit_returns_429_with_clear_message(client):
    for _ in range(LIMIT):
        await _chat(client)
    response = await _chat(client)
    assert response.status_code == 429
    assert "Trop de requêtes" in response.json()["detail"]


@pytest.mark.asyncio
async def test_chat_limit_resets_after_window(client):
    for _ in range(LIMIT):
        await _chat(client)
    assert (await _chat(client)).status_code == 429
    _wait_for_new_window()
    assert (await _chat(client)).status_code == 200


# ── /users/ ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_users_limit_is_shared_across_routes(client):
    user_id = uuid.uuid4()
    assert (await client.get("/users/")).status_code == 200
    assert (await client.get(f"/users/{user_id}")).status_code == 404
    assert (await client.delete(f"/users/{user_id}")).status_code == 404
    # 4e requête, sur une autre route encore : même compteur
    response = await client.put(f"/users/{user_id}", json={"is_active": True})
    assert response.status_code == 429
    assert "Trop de requêtes" in response.json()["detail"]


@pytest.mark.asyncio
async def test_users_limit_resets_after_window(client):
    for _ in range(LIMIT):
        await client.get("/users/")
    assert (await client.get("/users/")).status_code == 429
    _wait_for_new_window()
    assert (await client.get("/users/")).status_code == 200


@pytest.mark.asyncio
async def test_users_and_chat_limits_are_independent(client):
    for _ in range(LIMIT):
        await client.get("/users/")
    assert (await client.get("/users/")).status_code == 429
    assert (await _chat(client)).status_code == 200


# ── WebSocket ───────────────────────────────────────────────────────────

def _assert_rejected(ws, expected_text):
    data = ws.receive_json()
    assert data["error"] == "rate_limited"
    assert expected_text in data["response"]
    with pytest.raises(WebSocketDisconnect) as closed:
        ws.receive_text()
    assert closed.value.code == rate_limit.WS_POLICY_VIOLATION


def test_ws_messages_under_limit_pass():
    with TestClient(app).websocket_connect("/ws/test-a") as ws:
        for i in range(LIMIT):
            ws.send_text(f"message {i}")
            assert ws.receive_json()["response"] == f"écho : message {i}"


def test_ws_too_many_messages_closes_connection():
    with TestClient(app).websocket_connect("/ws/test-a") as ws:
        for i in range(LIMIT):
            ws.send_text(f"message {i}")
            ws.receive_json()
        ws.send_text("un de trop")
        _assert_rejected(ws, "Trop de messages")


def test_ws_message_limit_counts_all_connections_of_the_ip():
    client = TestClient(app)
    with client.websocket_connect("/ws/test-a") as ws:
        for i in range(LIMIT):
            ws.send_text(f"message {i}")
            ws.receive_json()
    # Nouvelle connexion, même IP : la limite n'est pas remise à zéro
    with client.websocket_connect("/ws/test-b") as ws:
        ws.send_text("un de trop")
        _assert_rejected(ws, "Trop de messages")


def test_ws_message_limit_resets_after_window():
    client = TestClient(app)
    with client.websocket_connect("/ws/test-a") as ws:
        for i in range(LIMIT):
            ws.send_text(f"message {i}")
            ws.receive_json()
    _wait_for_new_window()
    with client.websocket_connect("/ws/test-b") as ws:
        ws.send_text("de nouveau autorisé")
        assert ws.receive_json()["response"] == "écho : de nouveau autorisé"


def test_ws_too_many_simultaneous_connections_is_rejected():
    client = TestClient(app)
    with client.websocket_connect("/ws/test-a"), client.websocket_connect("/ws/test-b"):
        with client.websocket_connect("/ws/test-c") as third:
            _assert_rejected(third, "Trop de connexions")


def test_ws_closed_connection_frees_a_slot():
    client = TestClient(app)
    with client.websocket_connect("/ws/test-a"):
        with client.websocket_connect("/ws/test-b"):
            pass
        # test-b fermée : une nouvelle connexion est acceptée
        with client.websocket_connect("/ws/test-c") as ws:
            ws.send_text("bonjour")
            assert ws.receive_json()["response"] == "écho : bonjour"
