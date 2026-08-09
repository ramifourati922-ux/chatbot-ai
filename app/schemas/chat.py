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


class ChatResponse(BaseModel):
    """
    Réponse DU chatbot vers l'utilisateur.
    """
    response: str = Field(..., description="La réponse du chatbot")
    session_id: str = Field(..., description="ID de session à conserver")
    intent: Optional[str] = Field(None, description="Intent détecté")
    confidence: Optional[float] = Field(None, description="Score 0 à 1")
    sources: Optional[List[str]] = Field(default=[], description="Sources RAG")
    processing_time_ms: Optional[int] = Field(None, description="Temps en ms")
    escalated: bool = Field(default=False, description="Transféré à un humain ?")
    escalation_reason: Optional[str] = Field(
        None, description="Raison de l'escalade : explicit | frustration | repeated_rag_failure"
    )