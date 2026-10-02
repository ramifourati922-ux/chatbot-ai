# tests/test_login_throttling.py
"""
Échecs de connexion à /admin et /users/ limités (RATE_LIMIT_LOGIN_FAILURES).

Avant : aucun plafond, les essais de mot de passe refusés (401) n'étaient
pas comptés (l'authentification passe avant la limitation de débit), et
/admin n'avait aucune limite : attaque par force brute possible.
Désormais : après 5 échecs en 15 min par IP ou par identifiant, toute
tentative est refusée en 429, bon mot de passe compris. Les connexions
réussies ne comptent pas.
"""

import uuid

import httpx
import pytest
import pytest_asyncio

from app.api import auth, rate_limit
from app.config import settings
from app.main import app
from app.services.agent_auth import AuthenticatedAgent

GOOD = ("conseillere-test", "bon-mot-de-passe")


async def _fake_authenticate(username, password):
    if (username, password) == GOOD:
        return AuthenticatedAgent(id=uuid.uuid4(), username=username, role="conseiller")
    return None


@pytest.fixture(autouse=True)
def stub(monkeypatch):
    monkeypatch.setattr(auth, "authenticate", _fake_authenticate)  # ni base ni bcrypt
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN_FAILURES", "5/15 minutes")


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _me(client, username, password):
    return (await client.get("/admin/me", auth=(username, password))).status_code


@pytest.mark.asyncio
async def test_five_failures_then_even_the_right_password_is_refused(client):
    assert [await _me(client, GOOD[0], "faux") for _ in range(5)] == [401] * 5
    assert await _me(client, *GOOD) == 429


@pytest.mark.asyncio
async def test_successful_logins_are_never_counted(client):
    assert [await _me(client, *GOOD) for _ in range(20)] == [200] * 20


@pytest.mark.asyncio
async def test_failures_below_the_limit_do_not_block(client):
    for _ in range(4):
        assert await _me(client, GOOD[0], "faux") == 401
    assert await _me(client, *GOOD) == 200


@pytest.mark.asyncio
async def test_users_routes_are_protected_too(client):
    for _ in range(5):
        await client.get("/users/", auth=(GOOD[0], "faux"))
    assert (await client.get("/users/", auth=GOOD)).status_code == 429


def test_failures_are_counted_per_ip_and_per_username():
    """Attaque répartie : un même compte visé depuis plusieurs IP est bloqué ;
    une IP qui essaie plusieurs comptes aussi. Les autres ne le sont pas."""
    for i in range(5):
        rate_limit.login_failed(f"10.0.0.{i}", "cible")       # 5 IP différentes, même compte
    assert rate_limit.login_blocked("10.0.0.99", "cible")      # le compte est bloqué partout
    assert not rate_limit.login_blocked("10.0.0.99", "autre")  # pas les autres comptes

    for i in range(5):
        rate_limit.login_failed("10.0.0.50", f"compte-{i}")    # une IP, 5 comptes
    assert rate_limit.login_blocked("10.0.0.50", "nouveau")    # l'IP est bloquée
    assert not rate_limit.login_blocked("10.0.0.51", "nouveau")


def test_username_is_compared_case_insensitively():
    for _ in range(5):
        rate_limit.login_failed("10.0.1.1", "Admin")
    assert rate_limit.login_blocked("10.0.1.2", " admin ")
