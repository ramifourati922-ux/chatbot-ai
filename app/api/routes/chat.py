# app/api/routes/chat.py

from fastapi import APIRouter
import logging

from app.schemas.chat import ChatMessage, ChatResponse
from app.services.dialogue_manager import handle_message

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=ChatResponse)
async def chat(message: ChatMessage):
    """
    Endpoint principal du chatbot.
    Détection de langue + intent (règles) + RAG (ChromaDB) + LLM (Groq)
    orchestrés par dialogue_manager.handle_message().

    Note : pas de dépendance Postgres ici — la session vit dans Redis
    (session_manager), le contexte RAG dans ChromaDB, et l'appel LLM
    va vers Groq. Persister aussi l'historique en base (via
    ConversationRepository) est une amélioration possible mais hors
    scope de cette tâche.
    """
    result = await handle_message(
        message=message.message,
        session_id=message.session_id,
        channel=message.channel,
    )

    return ChatResponse(
        response=result.response,
        session_id=result.session_id,
        intent=result.intent,
        confidence=result.confidence,
        sources=[s for s in result.sources if s],
        processing_time_ms=result.processing_time_ms,
        escalated=result.escalated,
        escalation_reason=result.escalation_reason,
    )
