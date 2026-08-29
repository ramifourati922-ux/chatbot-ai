# app/services/dialogue_manager.py
"""
Orchestrateur central du chatbot — appelé par la route POST /chat.

Pour chaque message reçu :
1. Détection de la langue (language_detector) — imposée au LLM ensuite,
   pas laissée à sa devinette.
2. Classification d'intent par règles (intent_classifier) — rapide et
   gratuit, sert à détecter de façon fiable l'escalade humaine, qu'elle
   soit explicite ("je veux un agent") ou par frustration envers le
   service (pas question de laisser un LLM "peut-être" rater ces
   déclencheurs).
3. Si escalade demandée (explicite ou frustration) → réponse canned
   immédiate, pas d'appel LLM ; compteur de boucle RAG réinitialisé.
4. Sinon → recherche RAG dans la knowledge base (ChromaDB). Le compteur
   rag_attempts_count de la session est incrémenté à chaque passage ici ;
   à 3 échecs consécutifs (aucune escalade ni signal de satisfaction
   entre-temps), une escalade automatique est forcée sur CE message
   plutôt que de laisser le client tourner en boucle. Un signal de
   satisfaction explicite ("merci, c'est réglé"...) réinitialise aussi
   le compteur.
5. Si la recherche RAG aboutit mais avec une confiance trop faible
   (1 - distance du meilleur hit < RAG_CONFIDENCE_THRESHOLD, voir
   config.py pour la calibration) → escalade immédiate, PAS d'appel
   LLM : mieux vaut transférer que risquer une hallucination sur un
   sujet mal couvert par la base de connaissances.
6. Sinon → appel au LLM (Groq) avec le contexte trouvé.
7. Persistance de l'échange dans la session Redis (session_manager).

Les appels bloquants (embeddings, requête ChromaDB, appel Groq) sont
exécutés dans un thread (asyncio.to_thread) pour ne pas bloquer la
boucle d'événements FastAPI pendant qu'ils tournent.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from app.config import settings
from app.services.language_detector import detect_language
from app.services.intent_classifier import IntentClassifier
from app.services.session_manager import SessionManager
from app.services.rag import retriever
from app.services.rag.llm_factory import ask

logger = logging.getLogger(__name__)

_intent_classifier = IntentClassifier()
_session_manager = SessionManager()

# Messages d'escalade différenciés par raison — un client frustré reçoit
# un message qui reconnaît son mécontentement avant de transférer, plutôt
# que le même message neutre qu'une demande explicite.
ESCALATION_MESSAGES = {
    "explicit": {
        "fr": "Je vous mets en relation avec un conseiller humain. Quelqu'un va prendre le relais très rapidement.",
        "en": "I'm connecting you with a human agent. Someone will be with you shortly.",
        "ar": "سأقوم بتحويلك إلى أحد ممثلي خدمة العملاء. سيتواصل معك أحد الوكلاء قريباً.",
        "tn": "Bch na3addik l wa7ed agent humain, chwaya w ykhalmek 7ad mel service client.",
    },
    "frustration": {
        "fr": "Je comprends votre frustration et je suis désolé pour la gêne occasionnée. Je vous mets immédiatement en relation avec un conseiller humain qui pourra mieux vous aider.",
        "en": "I understand your frustration and I'm sorry for the inconvenience. I'm connecting you right away with a human agent who can better assist you.",
        "ar": "أتفهم انزعاجك وأعتذر عن الإزعاج. سأقوم بتحويلك فوراً إلى أحد ممثلي خدمة العملاء لمساعدتك بشكل أفضل.",
        "tn": "Nefhem 3lech mghadhab w n3tazer 3al mochkla. Bch na3addik tawa l wa7ed agent humain ykhalmek ahsen.",
    },
    "repeated_rag_failure": {
        "fr": "Je remarque que je n'arrive pas à répondre précisément à votre demande malgré plusieurs tentatives. Je vous mets en relation avec un conseiller humain qui pourra mieux vous aider.",
        "en": "I notice I haven't been able to answer your request precisely after a few tries. I'm connecting you with a human agent who can better assist you.",
        "ar": "ألاحظ أنني لم أتمكن من الإجابة على طلبك بدقة رغم عدة محاولات. سأقوم بتحويلك إلى أحد ممثلي خدمة العملاء لمساعدتك بشكل أفضل.",
        "tn": "Chft eli ma najjamtch njawbek b'des9a b3d 3adet mohawalet. Bch na3addik l wa7ed agent humain ykhalmek ahsen.",
    },
    "low_rag_confidence": {
        "fr": "Je ne dispose pas d'informations suffisamment fiables sur ce sujet précis. Je préfère vous mettre en relation avec un conseiller humain plutôt que de vous donner une réponse imprécise.",
        "en": "I don't have sufficiently reliable information on this specific topic. I'd rather connect you with a human agent than give you an imprecise answer.",
        "ar": "لا تتوفر لدي معلومات موثوقة بما فيه الكفاية حول هذا الموضوع بالتحديد. أفضل تحويلك إلى أحد ممثلي خدمة العملاء بدلاً من تقديم إجابة غير دقيقة.",
        "tn": "Ma3andich ma3loumet mou'akkada bidhabt 3al mawdhou3 hedha. Bch na3addik l wa7ed agent humain khir men najjawbek b'chay machi mou'akked.",
    },
}

# Nombre de messages RAG consécutifs (sans escalade ni signal de
# satisfaction) au-delà duquel on force une escalade automatique — le
# bot n'arrive visiblement pas à aider, mieux vaut transférer que de
# laisser le client tourner en boucle.
RAG_LOOP_THRESHOLD = 3


def _get_escalation_message(reason: Optional[str], language: str) -> str:
    """Message canned selon la raison d'escalade, avec repli sur
    "explicit"/fr si la raison ou la langue est inconnue."""
    by_language = ESCALATION_MESSAGES.get(reason) or ESCALATION_MESSAGES["explicit"]
    return by_language.get(language, by_language["fr"])


@dataclass
class DialogueResult:
    response: str
    session_id: str
    language: str
    intent: str
    confidence: float
    escalated: bool
    processing_time_ms: int
    sources: list = field(default_factory=list)
    escalation_reason: Optional[str] = None


async def handle_message(message: str, session_id: Optional[str] = None, channel: str = "web") -> DialogueResult:
    start = time.time()
    session_id = session_id or str(uuid.uuid4())

    # 1. Langue — détection rapide, pas de blocage nécessaire (pas d'I/O)
    language = detect_language(message)

    # 2. Intent (règles, rapide/gratuit)
    intent_result = _intent_classifier.classify(message)

    # 3. Session Redis (historique + contexte)
    await _session_manager.get_or_create(session_id, channel)
    await _session_manager.add_message(session_id, "user", message)

    # 4. Escalade (explicite ou frustration) → réponse immédiate, pas
    # d'appel LLM. Le compteur de boucle RAG repart de zéro : une
    # escalade "vide" la conversation, les échecs précédents ne comptent
    # plus après un transfert.
    if intent_result.requires_escalation:
        response_text = _get_escalation_message(intent_result.escalation_reason, language)
        await _session_manager.reset_rag_attempts(session_id)
        await _session_manager.add_message(
            session_id, "assistant", response_text,
            {"escalated": True, "escalation_reason": intent_result.escalation_reason},
        )
        processing_time = int((time.time() - start) * 1000)
        logger.info(
            f"🚨 Escalade humaine | raison={intent_result.escalation_reason} | "
            f"session={session_id} | langue={language}"
        )
        return DialogueResult(
            response=response_text, session_id=session_id, language=language,
            intent=intent_result.intent, confidence=intent_result.confidence,
            escalated=True, processing_time_ms=processing_time, sources=[],
            escalation_reason=intent_result.escalation_reason,
        )

    # 5. Signal de satisfaction ("merci, c'est réglé"...) → le client
    # indique que son problème est résolu, on repart de zéro sur le
    # compteur de boucle avant de continuer normalement vers le RAG.
    if _intent_classifier.is_satisfaction_signal(message):
        await _session_manager.reset_rag_attempts(session_id)
    else:
        # 6. Compteur de boucle RAG : trop d'échecs consécutifs sans
        # escalade ni satisfaction entre-temps → on force l'escalade sur
        # CE message plutôt que de laisser le client tourner en rond.
        rag_attempts = await _session_manager.increment_rag_attempts(session_id)
        if rag_attempts >= RAG_LOOP_THRESHOLD:
            response_text = _get_escalation_message("repeated_rag_failure", language)
            await _session_manager.reset_rag_attempts(session_id)
            await _session_manager.add_message(
                session_id, "assistant", response_text,
                {"escalated": True, "escalation_reason": "repeated_rag_failure"},
            )
            processing_time = int((time.time() - start) * 1000)
            logger.info(
                f"🚨 Escalade automatique (boucle RAG, {rag_attempts} tentatives) | "
                f"session={session_id} | langue={language}"
            )
            return DialogueResult(
                response=response_text, session_id=session_id, language=language,
                intent="repeated_rag_failure", confidence=1.0,
                escalated=True, processing_time_ms=processing_time, sources=[],
                escalation_reason="repeated_rag_failure",
            )

    # 7. RAG : recherche de contexte pertinent (bloquant → thread)
    # Pas de filtre par catégorie : retriever.search() sans type_filter
    # interroge déjà policy + product séparément puis fusionne (voir
    # retriever.py), ce qui couvre tous les cas sans distinction d'intent.
    hits = await asyncio.to_thread(retriever.search, message, 4)
    context = retriever.format_context(hits)
    sources = [hit["metadata"].get("source") or hit["metadata"].get("sku") for hit in hits]

    # 8. Confiance RAG trop faible → escalade immédiate, pas d'appel LLM.
    # Calculée APRÈS la recherche (impossible avant) mais AVANT l'appel
    # LLM (pas la peine de payer cet appel si on va escalader). Reset du
    # compteur de boucle comme pour les autres escalades — l'incrément
    # fait à l'étape 6 est annulé ici.
    #
    # LIMITE CONNUE (calibrée empiriquement, voir config.py) : sur notre
    # catalogue (~11 000 chunks produits + ~60 chunks de politiques), il
    # est en pratique très difficile de trouver une question DANS le
    # domaine Liss Strike (électronique/SAV) qui tombe sous le seuil —
    # la couverture du catalogue est trop large, même des questions sur
    # des services obscurs/inventés matchent au moins un peu. Sur ~18
    # questions candidates testées manuellement (fr + tunisien), seules
    # des questions clairement HORS domaine (ex: "combien de lunes a
    # Jupiter ?") sont descendues sous le seuil. Résultat concret : ce
    # mécanisme et le garde-fou hors-sujet du prompt système
    # (llm_factory.BASE_SYSTEM_PROMPT) se chevauchent largement en
    # pratique plutôt que de couvrir 2 cas bien distincts comme prévu à
    # la conception. Il reste utile en filet de sécurité supplémentaire
    # (rapide, pas d'appel LLM, donc moins cher) et pour le cas où hits
    # est complètement vide, mais NE PAS supposer qu'il isole finement
    # "hors-sujet" de "dans le domaine mais mal couvert" — dans les
    # faits, sur ce catalogue, il attrape surtout la même chose.
    rag_confidence = retriever.get_best_confidence(hits)
    if rag_confidence < settings.RAG_CONFIDENCE_THRESHOLD:
        response_text = _get_escalation_message("low_rag_confidence", language)
        await _session_manager.reset_rag_attempts(session_id)
        await _session_manager.add_message(
            session_id, "assistant", response_text,
            {"escalated": True, "escalation_reason": "low_rag_confidence", "rag_confidence": rag_confidence},
        )
        processing_time = int((time.time() - start) * 1000)
        logger.info(
            f"🚨 Escalade automatique (confiance RAG {rag_confidence:.3f} < "
            f"{settings.RAG_CONFIDENCE_THRESHOLD}) | session={session_id} | langue={language}"
        )
        return DialogueResult(
            response=response_text, session_id=session_id, language=language,
            intent="low_rag_confidence", confidence=rag_confidence,
            escalated=True, processing_time_ms=processing_time, sources=[],
            escalation_reason="low_rag_confidence",
        )

    # 9. Appel LLM (bloquant → thread)
    response_text = await asyncio.to_thread(ask, message, language, context)

    # 10. Persistance session
    await _session_manager.add_message(
        session_id, "assistant", response_text,
        {"intent": intent_result.intent, "sources": sources},
    )

    processing_time = int((time.time() - start) * 1000)
    logger.info(
        f"💬 intent={intent_result.intent} | langue={language} | "
        f"sources={len(sources)} | {processing_time}ms | session={session_id}"
    )

    return DialogueResult(
        response=response_text, session_id=session_id, language=language,
        intent=intent_result.intent, confidence=intent_result.confidence,
        escalated=False, processing_time_ms=processing_time, sources=sources,
    )
