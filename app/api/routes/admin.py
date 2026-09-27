# app/api/routes/admin.py
"""
Tableau de bord des conseillers : là où une escalade aboutit.

Quand le bot transfère un client à un humain, la conversation passe au
statut "escalated" en base (dialogue_manager._persist_exchange). Ces
routes permettent à un conseiller de voir les conversations en attente
et de marquer une prise en charge comme traitée (statut "resolved").

Protégé par HTTP Basic (ADMIN_USERNAME / ADMIN_PASSWORD dans .env) :
ces routes exposent les identifiants et les questions des clients.
Première barrière seulement : un seul compte partagé, pas de rôles, et
les identifiants circulent en clair (encodés en base64) → HTTPS
obligatoire en production.
"""

import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_db
from app.db.repositories.conversation_repository import ConversationRepository
from app.schemas.admin import EscalationItem, ResolveResponse

_REALM = "Liss Strike - conseillers"
# auto_error=True : sans en-tête Authorization, FastAPI répond déjà 401
# avec WWW-Authenticate (le navigateur affiche son invite de connexion).
_security = HTTPBasic(realm=_REALM)


def require_admin(credentials: HTTPBasicCredentials = Depends(_security)) -> str:
    """
    Vérifie l'identifiant et le mot de passe du conseiller.
    secrets.compare_digest : durée de comparaison indépendante du contenu
    (pas d'attaque par mesure du temps de réponse). Les deux comparaisons
    sont toujours faites, pour ne pas révéler lequel des deux est faux.
    """
    expected_password = settings.ADMIN_PASSWORD or ""
    username_ok = secrets.compare_digest(
        credentials.username.encode("utf-8"), settings.ADMIN_USERNAME.encode("utf-8")
    )
    password_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"), expected_password.encode("utf-8")
    )
    if not (expected_password and username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects",
            headers={"WWW-Authenticate": f'Basic realm="{_REALM}"'},
        )
    return credentials.username


router = APIRouter(tags=["Admin"], dependencies=[Depends(require_admin)])

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
