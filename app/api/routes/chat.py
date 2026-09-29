# app/api/routes/chat.py

from fastapi import APIRouter, HTTPException, Request
import logging

from app.api.rate_limit import chat_limit, limiter
from app.api.web_session import client_id_signature_valid, new_signed_client_id, web_session_id
from app.schemas.chat import ChatMessage, ChatResponse, WebSessionResponse
from app.services.dialogue_manager import handle_message

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)


@router.get("/session", response_model=WebSessionResponse)
async def new_web_session():
    """
    Identifiant de session web, attribué et signé par le serveur :
    /ws/{client_id} et POST /chat/ exigent la signature correspondante. Le
    navigateur ne choisit donc pas son identifiant, et ne peut pas
    reprendre celui d'un autre client.
    """
    client_id, signature = new_signed_client_id()
    return WebSessionResponse(client_id=client_id, signature=signature)


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
    # Identifiant attribué et signé par le serveur, comme pour /ws : sans
    # session_id, nouvelle session ; avec, la signature doit correspondre
    # (sinon 403, rien n'est traité). Un client ne peut donc ni choisir son
    # identifiant ni reprendre celui d'un autre en le devinant.
    if message.session_id is None:
        session_id, signature = new_signed_client_id()
    elif client_id_signature_valid(message.session_id, message.session_signature):
        session_id, signature = message.session_id, message.session_signature
    else:
        raise HTTPException(
            status_code=403,
            detail="session_id sans signature valide : omettez session_id pour ouvrir "
                   "une session, puis renvoyez le session_id et la session_signature reçus.",
        )
    # Préfixe "web:" (canal réel : cette route HTTP, quel que soit le
    # champ channel déclaré) : un session_id égal à un numéro WhatsApp ne
    # rejoint pas cette session (voir web_session.py). Le client reçoit
    # et renvoie son identifiant sans préfixe.
    result = await handle_message(
        message=message.message,
        session_id=web_session_id(session_id),
        channel=message.channel,
    )

    return ChatResponse(
        response=result.response,
        session_id=session_id,
        session_signature=signature,
        intent=result.intent,
        confidence=result.confidence,
        sources=[s for s in result.sources if s],
        processing_time_ms=result.processing_time_ms,
        escalated=result.escalated,
        escalation_reason=result.escalation_reason,
        handled_by_agent=result.handled_by_agent,
    )
