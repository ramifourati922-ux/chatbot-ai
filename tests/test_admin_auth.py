# tests/test_admin_auth.py
"""
Comptes conseillers et authentification HTTP Basic (/admin, /users/).

Chaque conseiller a son compte en base (table agents, mot de passe haché
bcrypt) ; rôles "conseiller" (conversations) et "admin" (en plus : comptes
conseillers et /users/). Compte admin d'amorçage créé depuis ADMIN_* si la
table est vide ; l'API refuse de démarrer si elle est vide sans
ADMIN_PASSWORD.
"""

import uuid
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select

from app import main
from app.api.routes import agents as agents_route
from app.config import settings
from app.db import database
from app.main import app
from app.models.agent import Agent
from app.services import agent_auth

CREATED = "test-nouveau-compte"  # supprimé par la fixture agent_accounts (conftest.CREATED)


def _routes():
    """Routes protégées : (méthode, chemin)."""
    return [
        ("GET", "/admin"),
        ("GET", "/admin/me"),
        ("GET", "/admin/escalations"),
        ("POST", f"/admin/escalations/{uuid.uuid4()}/resolve"),
        ("GET", f"/admin/escalations/{uuid.uuid4()}/messages"),
        ("POST", f"/admin/escalations/{uuid.uuid4()}/reply"),
        ("GET", "/admin/agents"),
    ]


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _assert_rejected(response):
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Basic")


# ── Authentification ───────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", _routes())
async def test_without_credentials_is_rejected(client, method, path):
    _assert_rejected(await client.request(method, path))


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", _routes())
async def test_wrong_password_is_rejected(client, agent_accounts, method, path):
    _assert_rejected(await client.request(method, path, auth=(agent_accounts.conseiller.username, "mauvais")))


@pytest.mark.asyncio
async def test_unknown_or_inactive_account_is_rejected(client, agent_accounts):
    _assert_rejected(await client.get("/admin/me", auth=("intrus", "mot-de-passe-conseiller")))
    _assert_rejected(await client.get("/admin/me", auth=agent_accounts.inactive.auth))


@pytest.mark.asyncio
async def test_each_agent_logs_in_with_his_own_account(client, agent_accounts):
    for account, role in ((agent_accounts.conseiller, "conseiller"), (agent_accounts.admin, "admin")):
        me = await client.get("/admin/me", auth=account.auth)
        assert me.status_code == 200
        assert me.json() == {"username": account.username, "role": role}


@pytest.mark.asyncio
async def test_password_is_stored_hashed(agent_accounts):
    async with database.AsyncSessionLocal() as db:
        agent = (await db.execute(select(Agent).where(Agent.id == agent_accounts.conseiller.id))).scalar_one()
    password = agent_accounts.conseiller.auth[1]
    assert agent.password_hash != password and password not in agent.password_hash
    assert agent.password_hash.startswith("$2b$")  # bcrypt
    assert agent_auth.verify_password(password, agent.password_hash)
    assert not agent_auth.verify_password("mauvais", agent.password_hash)


@pytest.mark.asyncio
async def test_env_admin_password_no_longer_authenticates(client, agent_accounts, monkeypatch):
    """Une fois les comptes en base, ADMIN_USERNAME / ADMIN_PASSWORD ne
    servent plus (seulement pour l'amorçage d'une table vide)."""
    monkeypatch.setattr(settings, "ADMIN_USERNAME", "admin-du-env")
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", "mot-de-passe-du-env")
    _assert_rejected(await client.get("/admin/me", auth=("admin-du-env", "mot-de-passe-du-env")))


@pytest.mark.asyncio
async def test_conseiller_uses_the_dashboard_normally(client, agent_accounts):
    auth = agent_accounts.conseiller.auth
    page = await client.get("/admin", auth=auth)
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    assert (await client.get("/admin/escalations", auth=auth)).status_code == 200
    # Conversation inconnue : la requête atteint bien la route (404, pas 401)
    assert (await client.post(f"/admin/escalations/{uuid.uuid4()}/resolve", auth=auth)).status_code == 404


# ── Rôles ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_conseiller_cannot_manage_accounts_or_users(client, agent_accounts):
    auth = agent_accounts.conseiller.auth
    assert (await client.get("/admin/agents", auth=auth)).status_code == 403
    assert (await client.post("/admin/agents", auth=auth,
                              json={"username": CREATED, "password": "12345678"})).status_code == 403
    assert (await client.get("/users/", auth=auth)).status_code == 403


@pytest.mark.asyncio
async def test_admin_manages_accounts(client, agent_accounts):
    auth = agent_accounts.admin.auth
    created = await client.post("/admin/agents", auth=auth,
                                json={"username": CREATED, "password": "premier-mot-de-passe"})
    assert created.status_code == 201
    body = created.json()
    assert body["role"] == "conseiller" and body["is_active"] is True and "password" not in str(body)
    assert (await client.get("/admin/me", auth=(CREATED, "premier-mot-de-passe"))).status_code == 200

    # Doublon refusé
    assert (await client.post("/admin/agents", auth=auth,
                              json={"username": CREATED, "password": "autre-mot-de-passe"})).status_code == 409
    listed = [a["username"] for a in (await client.get("/admin/agents", auth=auth)).json()]
    assert CREATED in listed

    # Changement de mot de passe
    assert (await client.put(f"/admin/agents/{body['id']}/password", auth=auth,
                             json={"password": "second-mot-de-passe"})).status_code == 204
    _assert_rejected(await client.get("/admin/me", auth=(CREATED, "premier-mot-de-passe")))
    assert (await client.get("/admin/me", auth=(CREATED, "second-mot-de-passe"))).status_code == 200

    # Désactivation puis réactivation
    assert (await client.post(f"/admin/agents/{body['id']}/deactivate", auth=auth)).json()["is_active"] is False
    _assert_rejected(await client.get("/admin/me", auth=(CREATED, "second-mot-de-passe")))
    assert (await client.post(f"/admin/agents/{body['id']}/activate", auth=auth)).json()["is_active"] is True
    assert (await client.get("/admin/me", auth=(CREATED, "second-mot-de-passe"))).status_code == 200


@pytest.mark.asyncio
async def test_password_over_72_bytes_is_refused(client, agent_accounts):
    # 40 caractères accentués = 80 octets : sous la limite de caractères, au-dessus de bcrypt
    response = await client.post("/admin/agents", auth=agent_accounts.admin.auth,
                                 json={"username": CREATED, "password": "é" * 40})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_last_active_admin_cannot_be_deactivated():
    admin = SimpleNamespace(role="admin", is_active=True)

    class OneAdminDb:
        async def get(self, model, agent_id):
            return admin

        async def scalar(self, query):
            return 1  # un seul admin actif

    with pytest.raises(Exception) as refused:
        await agents_route._set_active(OneAdminDb(), uuid.uuid4(), False)
    assert refused.value.status_code == 409
    assert admin.is_active is True


# ── Compte d'amorçage ──────────────────────────────────────────────────

class _FakeSession:
    def __init__(self, count):
        self.count, self.added, self.committed = count, [], False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def scalar(self, query):
        return self.count

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_bootstrap_creates_a_hashed_admin_when_table_is_empty(monkeypatch):
    session = _FakeSession(count=0)
    monkeypatch.setattr(agent_auth, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(agent_auth, "BCRYPT_ROUNDS", 4)
    monkeypatch.setattr(settings, "ADMIN_USERNAME", "premier-admin")
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", "mot-de-passe-initial")
    assert await agent_auth.bootstrap_admin_if_needed() == "created"
    [agent] = session.added
    assert (agent.username, agent.role, session.committed) == ("premier-admin", "admin", True)
    assert agent.password_hash != "mot-de-passe-initial"
    assert agent_auth.verify_password("mot-de-passe-initial", agent.password_hash)


@pytest.mark.asyncio
async def test_bootstrap_does_nothing_when_accounts_exist(monkeypatch):
    session = _FakeSession(count=2)
    monkeypatch.setattr(agent_auth, "AsyncSessionLocal", lambda: session)
    assert await agent_auth.bootstrap_admin_if_needed() == "exists"
    assert session.added == []


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", [None, ""])
async def test_api_refuses_to_start_without_accounts_nor_admin_password(monkeypatch, missing):
    monkeypatch.setattr(agent_auth, "AsyncSessionLocal", lambda: _FakeSession(count=0))
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", missing)
    with pytest.raises(RuntimeError, match="ADMIN_PASSWORD"):
        async with main.lifespan(app):
            pass
