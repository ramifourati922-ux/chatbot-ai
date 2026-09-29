# tests/test_users_auth.py
"""
Authentification HTTP Basic sur /users/ : comptes conseillers en base,
rôle admin exigé (require_admin, un conseiller reçoit 403, voir
test_admin_auth). Sans identifiants ou avec de mauvais identifiants : 401
+ WWW-Authenticate, sur les 5 routes. Avec un compte admin : la requête
atteint la route (dépôt des clients remplacé par des bouchons).
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio

from app.api import rate_limit
from app.config import settings
from app.db.database import get_db
from app.db.repositories.user_repository import UserRepository
from app.main import app

USER_ID = uuid.uuid4()


def _routes():
    """Les 5 routes de /users/ : (méthode, chemin, corps JSON)."""
    return [
        ("POST", "/users/", {"external_id": "test-auth", "channel": "web"}),
        ("GET", "/users/", None),
        ("GET", f"/users/{USER_ID}", None),
        ("PUT", f"/users/{USER_ID}", {"display_name": "Nouveau nom"}),
        ("DELETE", f"/users/{USER_ID}", None),
    ]


async def _fake_db():
    yield None


async def _created(self, user_data):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(), external_id=user_data.external_id, channel=user_data.channel,
        display_name=user_data.display_name, language=user_data.language, is_active=True,
        created_at=now, updated_at=now, last_seen_at=now,
    )


async def _no_user(self, *args, **kwargs):
    return None


async def _no_users(self, *args, **kwargs):
    return []


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(UserRepository, "create", _created)
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


def _assert_rejected(response):
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Basic")


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", _routes())
async def test_without_credentials_is_rejected(client, method, path, body):
    _assert_rejected(await client.request(method, path, json=body))


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", _routes())
async def test_wrong_password_is_rejected(client, agent_accounts, method, path, body):
    _assert_rejected(await client.request(method, path, json=body, auth=("test-admin-compte", "mauvais")))


@pytest.mark.asyncio
async def test_wrong_username_is_rejected(client, agent_accounts):
    _assert_rejected(await client.get("/users/", auth=("intrus", "mot-de-passe-admin")))


@pytest.mark.asyncio
async def test_correct_credentials_reach_every_route(client, agent_accounts):
    auth = agent_accounts.admin.auth
    expected = {
        ("POST", "/users/"): 201,
        ("GET", "/users/"): 200,
        ("GET", f"/users/{USER_ID}"): 404,     # inconnu : la route répond, pas l'auth
        ("PUT", f"/users/{USER_ID}"): 404,
        ("DELETE", f"/users/{USER_ID}"): 404,
    }
    for method, path, body in _routes():
        response = await client.request(method, path, json=body, auth=auth)
        assert response.status_code == expected[(method, path)], (method, path, response.text)
