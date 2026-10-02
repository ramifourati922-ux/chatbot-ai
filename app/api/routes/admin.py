# app/api/routes/admin.py
"""
Tableau de bord des conseillers : là où une escalade aboutit.

Quand le bot transfère un client à un humain, la conversation passe au
statut "escalated" en base (dialogue_manager._persist_exchange). Ces
routes permettent à un conseiller de voir les conversations en attente
et de marquer une prise en charge comme traitée (statut "resolved").

Protégé par HTTP Basic, un compte par conseiller (table agents, voir
app/api/auth.py) : ces routes exposent les identifiants et les questions
des clients. Réponses, prises en main et résolutions sont rattachées au
conseiller authentifié. Les identifiants circulent encodés en base64, non
chiffrés → HTTPS obligatoire en production.
"""

import csv
import io
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_agent

from app.api.routes import messenger, websocket, whatsapp
from app.api.web_session import WEB_SESSION_PREFIX
from app.config import settings
from app.log_privacy import safe_error
from app.db.database import get_db
from app.db.repositories.conversation_repository import ConversationRepository
from app.services import analytics
from app.services.agent_auth import AuthenticatedAgent
from app.services.dialogue_manager import record_agent_message
from app.schemas.admin import (
    ConversationHistory, CurrentAgent, EscalationItem, MessageItem, ReplyRequest, ReplyResponse,
    LeadItem, ResolveResponse, StatsResponse,
)

router = APIRouter(tags=["Admin"], dependencies=[Depends(require_agent)])

_ADMIN_PAGE = Path(__file__).resolve().parents[3] / "static" / "admin.html"
_STATS_PAGE = Path(__file__).resolve().parents[3] / "static" / "statistiques.html"


@router.get("/admin", include_in_schema=False)
async def admin_page():
    """Page HTML du tableau de bord (liste + bouton « Marquer traitée »)."""
    return FileResponse(_ADMIN_PAGE)


@router.get("/admin/statistiques", include_in_schema=False)
async def stats_page():
    """Page HTML des statistiques (taux d'automatisation, questions sans réponse)."""
    return FileResponse(_STATS_PAGE)


@router.get("/admin/stats", response_model=StatsResponse)
async def stats(days: int = Query(30, ge=1, le=365, description="Période, en jours"),
                db: AsyncSession = Depends(get_db)):
    """
    Indicateurs de la période : conversations traitées par le bot seul ou
    transférées, volumes par canal, langue et jour, réponses par type,
    transferts par raison, temps de réponse, et questions sans réponse
    (à ajouter à la base de connaissances). Voir app/services/analytics.py.
    """
    return await analytics.compute_stats(db, days)


@router.get("/admin/leads", response_model=List[LeadItem])
async def leads(days: int = Query(30, ge=1, le=365, description="Période, en jours"),
                limit: int = Query(50, ge=1, le=1000), db: AsyncSession = Depends(get_db)):
    """
    Prospects : clients qui se sont renseignés sur un produit, avec les
    produits d'intérêt, l'intention d'achat et le canal pour les recontacter.
    Intention d'achat d'abord, puis les plus récents.
    """
    return await analytics.compute_leads(db, days, limit)


def _csv_cell(value) -> str:
    """Neutralise une cellule qui serait lue comme une formule par un
    tableur (injection CSV) : le texte vient des messages des clients."""
    text_ = "" if value is None else str(value)
    return "'" + text_ if text_[:1] in ("=", "+", "-", "@", "\t", "\r") else text_


@router.get("/admin/leads.csv")
async def leads_csv(days: int = Query(30, ge=1, le=365), db: AsyncSession = Depends(get_db)):
    """Export des prospects pour le suivi commercial (séparateur « ; » et
    encodage UTF-8 avec BOM, lus directement par Excel en français)."""
    rows = await analytics.compute_leads(db, days, limit=1000)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["client", "canal", "recontactable", "langue", "premier_contact", "dernier_contact",
                     "questions_produit", "intention_achat", "produits", "derniere_question"])
    for lead in rows:
        writer.writerow([_csv_cell(v) for v in (
            lead["customer_id"], lead["channel"], "oui" if lead["recontactable"] else "non", lead["language"],
            lead["first_seen"].isoformat(timespec="minutes"), lead["last_seen"].isoformat(timespec="minutes"),
            lead["product_questions"], "oui" if lead["purchase_intent"] else "non",
            " | ".join(f"{p['name']} ({p['price_dt']:.2f} DT)" for p in lead["products"]), lead["last_question"],
        )])
    filename = f"prospects-{datetime.now(timezone.utc):%Y-%m-%d}.csv"
    return Response(content="﻿" + buffer.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/admin/me", response_model=CurrentAgent)
async def current_agent(agent: AuthenticatedAgent = Depends(require_agent)):
    """Conseiller connecté (affiché dans l'en-tête de la page)."""
    return CurrentAgent(username=agent.username, role=agent.role)


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
async def resolve_escalation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    agent: AuthenticatedAgent = Depends(require_agent),
):
    """Marque une escalade comme traitée, par le conseiller authentifié."""
    repo = ConversationRepository(db)
    conv = await repo.get_by_id(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    # "agent" : conversation prise en main, "Marquer traitée" rend la main au bot
    if conv.status not in ("escalated", "agent"):
        raise HTTPException(status_code=409, detail=f"Conversation non escaladée (statut : {conv.status})")
    resolved_at = datetime.now(timezone.utc)
    await repo.resolve(conversation_id, resolved_at, agent)
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
        conversation_id=conv.id, customer_id=customer_id, channel=channel,
        status=await repo.displayed_status(conv),
        messages=[
            MessageItem(
                role=m.role, content=m.content, created_at=m.created_at,
                agent=(m.metadata_ or {}).get("agent") if m.role == "agent" else None,
            )
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
            raise HTTPException(status_code=502, detail=f"Échec de l'envoi au client web : {safe_error(e)}")
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
        raise HTTPException(status_code=502, detail=f"Échec de l'envoi via {channel} : {safe_error(e)}")


@router.post("/admin/escalations/{conversation_id}/reply", response_model=ReplyResponse)
async def reply_to_customer(
    conversation_id: uuid.UUID,
    body: ReplyRequest,
    db: AsyncSession = Depends(get_db),
    agent: AuthenticatedAgent = Depends(require_agent),  # conseiller authentifié, conservé avec le message
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
    await repo.add_message(
        conv.id, "agent", text,
        {"agent": agent.username, "agent_id": str(agent.id), "sent_via": channel}, created_at=sent_at,
    )
    await repo.take_over(conv, agent, sent_at)
    await record_agent_message(customer_id, text)
    return ReplyResponse(conversation_id=conv.id, channel=channel, sent_at=sent_at)
