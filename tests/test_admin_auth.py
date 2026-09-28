# tests/test_admin_auth.py
"""
Authentification HTTP Basic du tableau de bord des conseillers (/admin).

Sans identifiants ou avec de mauvais identifiants : 401 + en-tête
WWW-Authenticate, sur les 3 routes. Avec les bons : comportement normal.
Et l'API refuse de démarrer si ADMIN_PASSWORD n'est pas défini.
"""

import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text

from app import main
from app.config import settings
from app.db import database
from app.main import app

USER, PASSWORD = "conseiller-test", "mot-de-passe-test"


def _routes():
    """Les 5 routes protégées : (méthode, chemin)."""
    return [
        ("GET", "/admin"),
        ("GET", "/admin/escalations"),
        ("POST", f"/admin/escalations/{uuid.uuid4()}/resolve"),
        ("GET", f"/admin/escalations/{uuid.uuid4()}/messages"),
        ("POST", f"/admin/escalations/{uuid.uuid4()}/reply"),
    ]


@pytest.fixture(autouse=True)
def admin_credentials(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_USERNAME", USER)
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", PASSWORD)


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _assert_rejected(response):
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Basic")


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", _routes())
async def test_without_credentials_is_rejected(client, method, path):
    _assert_rejected(await client.request(method, path))


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", _routes())
async def test_wrong_password_is_rejected(client, method, path):
    _assert_rejected(await client.request(method, path, auth=(USER, "mauvais")))


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", _routes())
async def test_wrong_username_is_rejected(client, method, path):
    _assert_rejected(await client.request(method, path, auth=("intrus", PASSWORD)))


@pytest.mark.asyncio
async def test_no_password_configured_rejects_everyone(client, monkeypatch):
    """Si ADMIN_PASSWORD est vide, même un mot de passe vide est refusé
    (l'API ne démarre de toute façon pas dans ce cas, voir plus bas)."""
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", None)
    _assert_rejected(await client.get("/admin/escalations", auth=(USER, "")))


@pytest.mark.asyncio
async def test_correct_credentials_give_normal_behaviour(client):
    auth = (USER, PASSWORD)
    page = await client.get("/admin", auth=auth)
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]

    try:
        async with database.AsyncSessionLocal() as db:
            await db.execute(text("select 1"))
    except Exception as e:
        pytest.skip(f"PostgreSQL indisponible : {e}")
    listing = await client.get("/admin/escalations", auth=auth)
    assert listing.status_code == 200 and isinstance(listing.json(), list)
    # Conversation inconnue : la requête atteint bien la route (404, pas 401)
    resolve = await client.post(f"/admin/escalations/{uuid.uuid4()}/resolve", auth=auth)
    assert resolve.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", [None, ""])
async def test_api_refuses_to_start_without_admin_password(monkeypatch, missing):
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", missing)
    with pytest.raises(RuntimeError, match="ADMIN_PASSWORD"):
        async with main.lifespan(app):
            pass
