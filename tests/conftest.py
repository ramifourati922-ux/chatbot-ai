# tests/conftest.py
"""
Fixtures partagées, et marqueur « integration ».

integration : test qui a besoin d'un service externe (PostgreSQL,
ChromaDB peuplé, Groq) ou qui charge un modèle d'embeddings / de
reranking. Tests unitaires seuls, sans aucun service, en quelques
secondes : pytest -m "not integration". Les tests qui utilisent une
fixture de base de données (DB_FIXTURES) sont marqués automatiquement ;
les autres portent @pytest.mark.integration (ou pytestmark du module).

agent_accounts : un compte admin et un compte conseiller en base (table
agents), supprimés après le test. Hachage bcrypt au coût minimal (4) pour
la rapidité des tests ; la vérification lit le coût dans le hachage, le
code de production reste inchangé (coût 12). Test ignoré si PostgreSQL
est indisponible. dispose(close=False) : une boucle asyncio par test, cf.
test_conversation_persistence.
"""

import hashlib
import hmac
import json
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import delete, text

from app.config import settings
from app.db import database
from app.models.agent import Agent
from app.services.agent_auth import hash_password

ADMIN = ("test-admin-compte", "mot-de-passe-admin")
CONSEILLER = ("test-conseiller-compte", "mot-de-passe-conseiller")
INACTIVE = ("test-inactif-compte", "mot-de-passe-inactif")
CREATED = "test-nouveau-compte"  # créé par les tests de gestion des comptes
TEST_USERNAMES = [ADMIN[0], CONSEILLER[0], INACTIVE[0], CREATED]


# Fixtures qui ouvrent une connexion PostgreSQL (tests ignorés sans base)
DB_FIXTURES = {"agent_accounts", "orders", "prefix", "session_prefix", "db_session_id"}


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: service externe requis (PostgreSQL, ChromaDB, Groq) ou modèle ML chargé")


def pytest_collection_modifyitems(config, items):
    for item in items:
        if DB_FIXTURES.intersection(getattr(item, "fixturenames", ())):
            item.add_marker(pytest.mark.integration)


async def _delete_test_agents():
    async with database.AsyncSessionLocal() as db:
        await db.execute(delete(Agent).where(Agent.username.in_(TEST_USERNAMES)))
        await db.commit()


@pytest_asyncio.fixture
async def agent_accounts():
    await database.engine.dispose(close=False)
    try:
        async with database.AsyncSessionLocal() as db:
            await db.execute(text("select 1 from agents limit 1"))
    except Exception as e:
        pytest.skip(f"PostgreSQL ou table agents indisponible : {e}")
    await _delete_test_agents()  # reste d'une exécution interrompue
    async with database.AsyncSessionLocal() as db:
        accounts = {}
        for key, (username, password), role, active in [
            ("admin", ADMIN, "admin", True),
            ("conseiller", CONSEILLER, "conseiller", True),
            ("inactive", INACTIVE, "conseiller", False),
        ]:
            agent = Agent(username=username, password_hash=hash_password(password, rounds=4),
                          role=role, is_active=active)
            db.add(agent)
            await db.flush()
            accounts[key] = SimpleNamespace(id=agent.id, username=username, auth=(username, password))
        await db.commit()
    yield SimpleNamespace(**accounts)
    await database.engine.dispose(close=False)
    await _delete_test_agents()
    await database.engine.dispose(close=False)


@pytest.fixture
def sign_whatsapp(monkeypatch):
    """
    Secret d'application de test, et fonction qui signe un corps de requête
    comme Meta (HMAC-SHA256, en-tête X-Hub-Signature-256). Le webhook refuse
    toute requête non signée : les tests passent par ici.
    Usage : body, headers = sign_whatsapp(payload)
    """
    test_secret = "cle-de-test-webhook-whatsapp"
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", test_secret)

    def sign(payload: dict):
        body = json.dumps(payload).encode("utf-8")
        signature = hmac.new(test_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return body, {"Content-Type": "application/json", "X-Hub-Signature-256": f"sha256={signature}"}

    return sign
