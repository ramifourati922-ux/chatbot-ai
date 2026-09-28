# app/api/routes/chat.py

from fastapi import APIRouter, Request
import logging
import uuid

from app.api.rate_limit import chat_limit, limiter
from app.api.web_session import web_session_id
from app.schemas.chat import ChatMessage, ChatResponse
from app.services.dialogue_manager import handle_message

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=ChatResponse)
@limiter.limit(chat_limit)  # 429 au-delà de RATE_LIMIT_CHAT par IP
async def chat(request: Request, message: ChatMessage):
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
    # Préfixe "web:" (canal réel : cette route HTTP, quel que soit le
    # champ channel déclaré) : un session_id égal à un numéro WhatsApp ne
    # rejoint pas cette session (voir web_session.py). Le client reçoit
    # et renvoie son identifiant sans préfixe.
    session_id = message.session_id or str(uuid.uuid4())
    result = await handle_message(
        message=message.message,
        session_id=web_session_id(session_id),
        channel=message.channel,
    )

    return ChatResponse(
        response=result.response,
        session_id=session_id,
        intent=result.intent,
        confidence=result.confidence,
        sources=[s for s in result.sources if s],
        processing_time_ms=result.processing_time_ms,
        escalated=result.escalated,
        escalation_reason=result.escalation_reason,
        handled_by_agent=result.handled_by_agent,
    )
