# app/api/routes/admin.py
"""
Tableau de bord des conseillers : là où une escalade aboutit.

Quand le bot transfère un client à un humain, la conversation passe au
statut "escalated" en base (dialogue_manager._persist_exchange). Ces
routes permettent à un conseiller de voir les conversations en attente
et de marquer une prise en charge comme traitée (statut "resolved").

⚠️ Pas d'authentification pour l'instant, comme le reste de l'API
(limite documentée) : à protéger avant toute mise en ligne, ces routes
exposent les identifiants et les questions des clients.
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.repositories.conversation_repository import ConversationRepository
from app.schemas.admin import EscalationItem, ResolveResponse

router = APIRouter(tags=["Admin"])

_ADMIN_PAGE = Path(__file__).resolve().parents[3] / "static" / "admin.html"


@router.get("/admin", include_in_schema=False)
async def admin_page():
    """Page HTML du tableau de bord (liste + bouton « Marquer traitée »)."""
    return FileResponse(_ADMIN_PAGE)


@router.get("/admin/escalations", response_model=List[EscalationItem])
async def list_escalations(db: AsyncSession = Depends(get_db)):
    """Conversations transférées en attente d'un conseiller, la plus récente en premier."""
    now = datetime.now(timezone.utc)
    escalations = await ConversationRepository(db).list_escalated()
    return [
        EscalationItem(**e, waiting_seconds=max(0, int((now - e["escalated_at"]).total_seconds())))
        for e in escalations
    ]


@router.post("/admin/escalations/{conversation_id}/resolve", response_model=ResolveResponse)
async def resolve_escalation(conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Marque une escalade comme traitée par un conseiller."""
    repo = ConversationRepository(db)
    conv = await repo.get_by_id(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    if conv.status != "escalated":
        raise HTTPException(status_code=409, detail=f"Conversation non escaladée (statut : {conv.status})")
    resolved_at = datetime.now(timezone.utc)
    await repo.resolve(conversation_id, resolved_at)
    return ResolveResponse(conversation_id=conversation_id, status="resolved", resolved_at=resolved_at)
