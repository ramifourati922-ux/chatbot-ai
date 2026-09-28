# tests/test_cors.py
"""
Restriction CORS : seules les origines de CORS_ALLOWED_ORIGINS reçoivent
les en-têtes CORS permissifs. Une origine inconnue n'en reçoit aucun (le
navigateur bloque alors la lecture de la réponse). /chat-demo, servi par
l'API elle-même, n'est pas concerné (même origine).
"""

import httpx
import pytest
import pytest_asyncio

from app.config import DEFAULT_CORS_ORIGINS, Settings, settings
from app.main import app

EVIL = "https://evil.test"


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _allowed_origin():
    return settings.cors_origins[0]


# ── Lecture de CORS_ALLOWED_ORIGINS ─────────────────────────────────────

@pytest.mark.parametrize("raw", ["", "   ", " , ,"])
def test_missing_or_empty_value_falls_back_to_local_origins(raw):
    s = Settings(DATABASE_URL="postgresql+asyncpg://x/y", CORS_ALLOWED_ORIGINS=raw)
    assert s.cors_origins == list(DEFAULT_CORS_ORIGINS)


def test_comma_separated_list_is_trimmed():
    s = Settings(
        DATABASE_URL="postgresql+asyncpg://x/y",
        CORS_ALLOWED_ORIGINS=" http://localhost:8000 , https://demo.ngrok-free.app ,",
    )
    assert s.cors_origins == ["http://localhost:8000", "https://demo.ngrok-free.app"]


# ── Comportement du middleware ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_allowed_origin_receives_cors_headers(client):
    origin = _allowed_origin()
    response = await client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


@pytest.mark.asyncio
async def test_unknown_origin_receives_no_cors_headers(client):
    response = await client.get("/health", headers={"Origin": EVIL})
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.asyncio
async def test_preflight_from_allowed_origin_is_accepted(client):
    origin = _allowed_origin()
    response = await client.options("/chat/", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


@pytest.mark.asyncio
async def test_preflight_from_unknown_origin_is_rejected(client):
    response = await client.options("/chat/", headers={
        "Origin": EVIL,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.asyncio
async def test_chat_demo_same_origin_still_served(client):
    # Même origine : le navigateur n'envoie pas de requête CORS
    response = await client.get("/chat-demo")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
