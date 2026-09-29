# tests/conftest.py
"""
Fixtures partagées.

agent_accounts : un compte admin et un compte conseiller en base (table
agents), supprimés après le test. Hachage bcrypt au coût minimal (4) pour
la rapidité des tests ; la vérification lit le coût dans le hachage, le
code de production reste inchangé (coût 12). Test ignoré si PostgreSQL
est indisponible. dispose(close=False) : une boucle asyncio par test, cf.
test_conversation_persistence.
"""

from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import delete, text

from app.db import database
from app.models.agent import Agent
from app.services.agent_auth import hash_password

ADMIN = ("test-admin-compte", "mot-de-passe-admin")
CONSEILLER = ("test-conseiller-compte", "mot-de-passe-conseiller")
INACTIVE = ("test-inactif-compte", "mot-de-passe-inactif")
CREATED = "test-nouveau-compte"  # créé par les tests de gestion des comptes
TEST_USERNAMES = [ADMIN[0], CONSEILLER[0], INACTIVE[0], CREATED]


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
