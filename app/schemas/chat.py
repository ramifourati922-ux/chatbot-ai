# app/schemas/chat.py
"""
Schémas pour les messages du chatbot.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
import uuid


class ChatMessage(BaseModel):
    """
    Message envoyé AU chatbot par l'utilisateur.
    POST /chat → ce schéma valide le body.
    """
    message: str = Field(
        ...,              # ... = obligatoire
        min_length=1,
        max_length=5000,
        description="Le message de l'utilisateur"
    )
    session_id: Optional[str] = Field(
        None,
        description="ID de session (pour continuer une conversation)"
    )
    channel: str = Field(
        default="web",
        description="Canal d'où vient le message"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Bonjour, où est ma commande #CMD12345 ?",
                "channel": "web"
            }
        }


class WebSessionResponse(BaseModel):
    """Identifiant de session WebSocket attribué et signé par le serveur
    (GET /chat/session), à présenter à /ws/{client_id}?signature=..."""
    client_id: str
    signature: str


class ChatResponse(BaseModel):
    """
    Réponse DU chatbot vers l'utilisateur.
    """
    response: str = Field(..., description="La réponse du chatbot")
    session_id: str = Field(..., description="ID de session à conserver")
    intent: Optional[str] = Field(None, description="Intent détecté")
    confidence: Optional[float] = Field(
        None,
        description="Score 0 à 1. Réponse RAG ou escalade low_rag_confidence : confiance de la "
                    "recherche RAG. Escalade explicite/frustration ou politesse : confiance du "
                    "classifieur d'intentions.",
    )
    sources: Optional[List[str]] = Field(default=[], description="Sources RAG")
    processing_time_ms: Optional[int] = Field(None, description="Temps en ms")
    escalated: bool = Field(default=False, description="Transféré à un humain ?")
    escalation_reason: Optional[str] = Field(
        None, description="Raison de l'escalade : explicit | frustration | repeated_rag_failure | low_rag_confidence"
    )
    handled_by_agent: bool = Field(
        default=False,
        description="Un conseiller a pris la main sur la conversation : le bot ne répond pas (response vide)",
    )