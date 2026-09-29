# app/api/routes/agents.py
"""
Gestion des comptes conseillers — rôle admin uniquement.

Pas d'écran dédié dans /admin : ces routes s'utilisent depuis /docs
(Swagger gère HTTP Basic) ou curl. Le mot de passe est haché (bcrypt)
avant d'être enregistré, et n'est jamais renvoyé.

Garde-fou : on ne peut pas désactiver ni rétrograder le dernier admin
actif (plus personne ne pourrait gérer les comptes).
"""

import asyncio
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_admin
from app.db.database import get_db
from app.models.agent import Agent
from app.schemas.admin import AgentCreate, AgentOut, AgentPassword
from app.services.agent_auth import hash_password

router = APIRouter(prefix="/admin/agents", tags=["Admin — comptes conseillers"],
                   dependencies=[Depends(require_admin)])


async def _get(db: AsyncSession, agent_id: uuid.UUID) -> Agent:
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Conseiller introuvable")
    return agent


async def _hash(password: str) -> str:
    try:
        return await asyncio.to_thread(hash_password, password)
    except ValueError as e:  # plus de 72 octets (caractères accentués comptés en octets)
        raise HTTPException(status_code=422, detail=str(e))


@router.get("", response_model=List[AgentOut])
async def list_agents(db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(Agent).order_by(Agent.created_at))).scalars().all()


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
async def create_agent(body: AgentCreate, db: AsyncSession = Depends(get_db)):
    if await db.scalar(select(Agent).where(Agent.username == body.username)):
        raise HTTPException(status_code=409, detail=f"Le compte « {body.username} » existe déjà")
    agent = Agent(username=body.username, password_hash=await _hash(body.password), role=body.role)
    db.add(agent)
    await db.flush()
    await db.refresh(agent)
    return agent


async def _set_active(db: AsyncSession, agent_id: uuid.UUID, active: bool) -> Agent:
    agent = await _get(db, agent_id)
    if not active and agent.role == "admin" and agent.is_active:
        active_admins = await db.scalar(
            select(func.count()).select_from(Agent).where(Agent.role == "admin", Agent.is_active.is_(True))
        )
        if active_admins <= 1:
            raise HTTPException(status_code=409, detail="Impossible de désactiver le dernier admin actif")
    agent.is_active = active
    await db.flush()
    return agent


@router.post("/{agent_id}/deactivate", response_model=AgentOut)
async def deactivate_agent(agent_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Le compte ne peut plus se connecter ; son historique (traçabilité) est conservé."""
    return await _set_active(db, agent_id, False)


@router.post("/{agent_id}/activate", response_model=AgentOut)
async def activate_agent(agent_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _set_active(db, agent_id, True)


@router.put("/{agent_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def set_agent_password(agent_id: uuid.UUID, body: AgentPassword, db: AsyncSession = Depends(get_db)):
    agent = await _get(db, agent_id)
    agent.password_hash = await _hash(body.password)
    await db.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
