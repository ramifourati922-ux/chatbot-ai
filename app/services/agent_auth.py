# app/services/agent_auth.py
"""
Comptes conseillers : hachage des mots de passe, authentification et
compte d'amorçage.

- Mots de passe hachés avec bcrypt (sel aléatoire, coût 12), jamais
  stockés ni journalisés en clair. bcrypt est volontairement lent : la
  vérification tourne dans un thread pour ne pas bloquer le serveur.
- Identifiant inconnu : un hachage factice est quand même vérifié, pour
  que le temps de réponse ne révèle pas quels comptes existent.
- Amorçage : si la table agents est vide, un compte admin est créé à
  partir de ADMIN_USERNAME / ADMIN_PASSWORD (.env). Ensuite ces variables
  ne servent plus : les comptes vivent en base.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Optional

import bcrypt
from sqlalchemy import func, select

from app.config import settings
from app.db.database import AsyncSessionLocal
from app.models.agent import Agent

logger = logging.getLogger(__name__)

BCRYPT_ROUNDS = 12
# bcrypt ne prend en compte que les 72 premiers octets (et bcrypt 5 refuse
# au-delà) : limite imposée à la création plutôt que tronquée en silence.
MAX_PASSWORD_BYTES = 72
_dummy_hash: Optional[bytes] = None


@dataclass(frozen=True)
class AuthenticatedAgent:
    """Conseiller authentifié pour la requête en cours."""
    id: uuid.UUID
    username: str
    role: str


def hash_password(password: str, rounds: int = BCRYPT_ROUNDS) -> str:
    raw = password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Mot de passe trop long (maximum {MAX_PASSWORD_BYTES} octets)")
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:  # mot de passe > 72 octets ou hachage invalide
        return False


def _verify_or_burn_time(password: str, agent: Optional[Agent]) -> bool:
    global _dummy_hash
    if agent is None:
        if _dummy_hash is None:
            _dummy_hash = bcrypt.hashpw(b"compte-inexistant", bcrypt.gensalt(BCRYPT_ROUNDS))
        bcrypt.checkpw(password.encode("utf-8")[:MAX_PASSWORD_BYTES], _dummy_hash)
        return False
    return verify_password(password, agent.password_hash)


async def authenticate(username: str, password: str) -> Optional[AuthenticatedAgent]:
    """Le conseiller si l'identifiant existe, est actif et que le mot de
    passe correspond ; None sinon (sans dire lequel des trois a échoué)."""
    async with AsyncSessionLocal() as db:
        agent = (await db.execute(select(Agent).where(Agent.username == username))).scalar_one_or_none()
    ok = await asyncio.to_thread(_verify_or_burn_time, password, agent)
    if not ok or not agent.is_active:
        return None
    return AuthenticatedAgent(id=agent.id, username=agent.username, role=agent.role)


async def bootstrap_admin_if_needed() -> str:
    """
    "exists" si au moins un compte existe ; "created" si le compte admin
    d'amorçage vient d'être créé depuis ADMIN_USERNAME / ADMIN_PASSWORD ;
    "missing_password" si la table est vide et ADMIN_PASSWORD absent.
    """
    async with AsyncSessionLocal() as db:
        if await db.scalar(select(func.count()).select_from(Agent)):
            return "exists"
        if not settings.ADMIN_PASSWORD:
            return "missing_password"
        password_hash = await asyncio.to_thread(hash_password, settings.ADMIN_PASSWORD)
        db.add(Agent(username=settings.ADMIN_USERNAME, password_hash=password_hash, role="admin"))
        await db.commit()
    logger.info(f"👤 Compte admin d'amorçage créé : {settings.ADMIN_USERNAME} "
                f"(ADMIN_USERNAME / ADMIN_PASSWORD ne servent plus ensuite)")
    return "created"
