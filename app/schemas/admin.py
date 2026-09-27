# app/schemas/admin.py
"""Schémas du tableau de bord des conseillers (routes /admin)."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EscalationItem(BaseModel):
    """Une conversation transférée qui attend un conseiller."""
    conversation_id: uuid.UUID
    customer_id: Optional[str] = Field(None, description="Identifiant du client sur son canal (n° WhatsApp, PSID, session web)")
    channel: str = Field(..., description="web | whatsapp | messenger")
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
