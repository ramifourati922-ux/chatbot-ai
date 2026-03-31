# app/api/routes/chat.py

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uuid, time, logging

from app.db.database import get_db
from app.schemas.chat import ChatMessage, ChatResponse

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=ChatResponse)
async def chat(
    message: ChatMessage,
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint principal du chatbot.
    Phase 1 : réponses simulées
    Phase 2 : moteur de règles
    Phase 3 : RAG + LLM
    """
    start_time = time.time()
    session_id = message.session_id or str(uuid.uuid4())

    # Détection basique d'intent
    text = message.message.lower()

    if any(w in text for w in ["bonjour", "salut", "hello"]):
        response = "Bonjour ! Je suis votre assistant IA. Comment puis-je vous aider ?"
        intent = "greeting"
    elif any(w in text for w in ["commande", "colis", "livraison"]):
        response = "Je vais vérifier votre commande. Pouvez-vous me donner votre numéro de commande ?"
        intent = "check_order"
    elif any(w in text for w in ["retour", "rembours"]):
        response = "Je vais vous aider avec votre retour. Quel est votre numéro de commande ?"
        intent = "return_request"
    elif any(w in text for w in ["prix", "coût", "combien"]):
        response = "Je peux vous renseigner sur les prix. Quel produit vous intéresse ?"
        intent = "price_inquiry"
    else:
        response = "Je comprends votre demande. Pouvez-vous me donner plus de détails ?"
        intent = "unknown"

    processing_time = int((time.time() - start_time) * 1000)
    logger.info(f"💬 Intent: {intent} | Temps: {processing_time}ms")

    return ChatResponse(
        response=response,
        session_id=session_id,
        intent=intent,
        confidence=0.85,
        processing_time_ms=processing_time,
        escalated=False
    )