# app/schemas/admin.py
"""Schémas du tableau de bord des conseillers (routes /admin)."""

import uuid
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class EscalationItem(BaseModel):
    """Une conversation transférée qui attend un conseiller."""
    conversation_id: uuid.UUID
    customer_id: Optional[str] = Field(None, description="Identifiant du client sur son canal (n° WhatsApp, PSID, session web)")
    channel: str = Field(..., description="web | whatsapp | messenger")
    status: str = Field("escalated", description="escalated (en attente) | agent (pris en main par un conseiller)")
    taken_over_by: Optional[str] = Field(None, description="Conseiller qui a pris la main (statut agent)")
    last_question: str = Field(..., description="Question du client qui a déclenché le transfert")
    reason: Optional[str] = Field(
        None, description="explicit | frustration | low_rag_confidence | repeated_rag_failure"
    )
    escalated_at: datetime
    waiting_seconds: int = Field(..., description="Temps d'attente depuis le transfert, en secondes")


class ResolveResponse(BaseModel):
    conversation_id: uuid.UUID
    status: str
    resolved_at: datetime


class MessageItem(BaseModel):
    """Un message de l'historique d'une conversation."""
    role: str = Field(..., description="user (client) | assistant (bot) | agent (conseiller)")
    content: str
    created_at: datetime
    agent: Optional[str] = Field(None, description="Conseiller qui a écrit le message (rôle agent)")


class ConversationHistory(BaseModel):
    conversation_id: uuid.UUID
    customer_id: Optional[str]
    channel: str = Field(..., description="Canal réel de la conversation : web | whatsapp | messenger")
    status: str
    messages: List[MessageItem]


class ReplyRequest(BaseModel):
    # 4 096 caractères : limite d'un message texte WhatsApp
    text: str = Field(..., min_length=1, max_length=4096, description="Réponse du conseiller au client")


class ReplyResponse(BaseModel):
    conversation_id: uuid.UUID
    channel: str
    sent_at: datetime


class CurrentAgent(BaseModel):
    username: str
    role: str


# ── Gestion des comptes conseillers (rôle admin) ──────────────────────
class AgentCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Za-z0-9._-]+$")
    # 72 octets : limite de bcrypt (vérifiée aussi en octets à la création)
    password: str = Field(..., min_length=8, max_length=72)
    role: Literal["admin", "conseiller"] = "conseiller"


class AgentPassword(BaseModel):
    password: str = Field(..., min_length=8, max_length=72)


class AgentOut(BaseModel):
    id: uuid.UUID
    username: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
