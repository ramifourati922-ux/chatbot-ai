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
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import messenger, websocket, whatsapp
from app.api.web_session import WEB_SESSION_PREFIX
from app.config import settings
from app.db.database import get_db
from app.db.repositories.conversation_repository import ConversationRepository
from app.services.dialogue_manager import record_agent_message
from app.schemas.admin import (
    ConversationHistory, EscalationItem, MessageItem, ReplyRequest, ReplyResponse, ResolveResponse,
)

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
    # "agent" : conversation prise en main, "Marquer traitée" rend la main au bot
    if conv.status not in ("escalated", "agent"):
        raise HTTPException(status_code=409, detail=f"Conversation non escaladée (statut : {conv.status})")
    resolved_at = datetime.now(timezone.utc)
    await repo.resolve(conversation_id, resolved_at)
    return ResolveResponse(conversation_id=conversation_id, status="resolved", resolved_at=resolved_at)


def _real_channel(conv_channel: str, customer_id: Optional[str]) -> str:
    """
    Canal par lequel joindre le client. Un identifiant "web:..." désigne
    toujours le chat du site : le champ channel de POST /chat/ est déclaratif,
    une conversation web peut donc être enregistrée sous "whatsapp". Lui
    répondre sur WhatsApp enverrait le message à un faux numéro.
    """
    if customer_id and customer_id.startswith(WEB_SESSION_PREFIX):
        return "web"
    return conv_channel


async def _load(repo: ConversationRepository, conversation_id: uuid.UUID) -> tuple:
    found = await repo.get_with_customer(conversation_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    conv, customer_id = found
    return conv, customer_id, _real_channel(conv.channel, customer_id)


@router.get("/admin/escalations/{conversation_id}/messages", response_model=ConversationHistory)
async def conversation_history(conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Historique complet de la conversation, dans l'ordre chronologique."""
    repo = ConversationRepository(db)
    conv, customer_id, channel = await _load(repo, conversation_id)
    return ConversationHistory(
        conversation_id=conv.id, customer_id=customer_id, channel=channel, status=conv.status,
        messages=[
            MessageItem(role=m.role, content=m.content, created_at=m.created_at)
            for m in await repo.get_full_history(conv.id)
        ],
    )


def _meta_send_function(channel: str):
    """
    Fonction d'envoi EXISTANTE du canal (celle des webhooks, réutilisée
    telle quelle), ou None si les identifiants Meta manquent.

    Ils sont vérifiés ICI, avec les mêmes conditions que ces fonctions :
    sans eux, elles ne lèvent pas d'erreur mais simulent l'envoi (simple
    avertissement dans les logs). Le conseiller croirait alors son message
    parti alors que le client ne l'a jamais reçu. Appel via le module
    (whatsapp._send_whatsapp_message) : remplaçable dans les tests, sans
    jamais contacter Meta.
    """
    if channel == "whatsapp" and settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID:
        return whatsapp._send_whatsapp_message
    if channel == "messenger" and settings.MESSENGER_PAGE_ACCESS_TOKEN:
        return messenger._send_messenger_message
    return None


async def _send_to_customer(channel: str, customer_id: str, text: str) -> None:
    """Envoie la réponse du conseiller sur le canal réel, ou lève une
    HTTPException explicite : 409 si l'envoi est impossible en l'état,
    502 si le canal a échoué."""
    if channel == "web":
        # Seule une connexion WebSocket ouverte permet de joindre un client
        # web : pas de numéro à rappeler. Client parti ou venu par POST /chat/
        # (sans connexion) : injoignable, le conseiller doit le savoir.
        client_id = customer_id.removeprefix(WEB_SESSION_PREFIX)
        try:
            delivered = await websocket.manager.send_to(client_id, {
                "response": text, "from_agent": True, "escalated": False, "intent": "agent",
            })
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Échec de l'envoi au client web : {e}")
        if not delivered:
            raise HTTPException(
                status_code=409,
                detail="Client web injoignable : il n'est plus connecté au chat du site "
                       "(onglet fermé, ou message envoyé sans connexion temps réel).",
            )
        return

    send = _meta_send_function(channel)
    if send is None:
        raise HTTPException(
            status_code=409,
            detail=f"Envoi impossible sur le canal « {channel} » : identifiants Meta non "
                   "configurés (voir WHATSAPP_* / MESSENGER_* dans .env).",
        )
    try:
        await send(customer_id, text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Échec de l'envoi via {channel} : {e}")


@router.post("/admin/escalations/{conversation_id}/reply", response_model=ReplyResponse)
async def reply_to_customer(
    conversation_id: uuid.UUID,
    body: ReplyRequest,
    db: AsyncSession = Depends(get_db),
    agent: str = Depends(require_admin),  # identifiant du conseiller, conservé avec le message
):
    """
    Le conseiller répond au client, sur le canal d'origine de la conversation.
    Le message est enregistré (rôle "agent") seulement si l'envoi a réussi,
    et le conseiller prend la main : le bot ne répond plus à ce client
    (statut "agent") jusqu'à "Marquer traitée" ou 1 h sans message du
    conseiller (voir dialogue_manager.agent_has_the_conversation).
    """
    repo = ConversationRepository(db)
    conv, customer_id, channel = await _load(repo, conversation_id)
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Message vide")

    await _send_to_customer(channel, customer_id, text)

    sent_at = datetime.now(timezone.utc)
    await repo.add_message(conv.id, "agent", text, {"agent": agent, "sent_via": channel}, created_at=sent_at)
    await repo.take_over(conv, agent, sent_at)
    await record_agent_message(customer_id, text)
    return ReplyResponse(conversation_id=conv.id, channel=channel, sent_at=sent_at)
