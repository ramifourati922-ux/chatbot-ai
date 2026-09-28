# app/services/dialogue_manager.py
"""
Orchestrateur central du chatbot — appelé par la route POST /chat.

Pour chaque message reçu :
0. Si un conseiller a pris la main sur la conversation depuis /admin
   (statut "agent", voir agent_has_the_conversation), le bot ne répond
   pas : le message du client est seulement enregistré.
1. Détection de la langue (language_detector) — imposée au LLM ensuite,
   pas laissée à sa devinette.
2. Classification d'intent par règles (intent_classifier) — rapide et
   gratuit, sert à détecter de façon fiable l'escalade humaine, qu'elle
   soit explicite ("je veux un agent") ou par frustration envers le
   service (pas question de laisser un LLM "peut-être" rater ces
   déclencheurs).
3. Si escalade demandée (explicite ou frustration) → réponse canned
   immédiate, pas d'appel LLM ; compteur de boucle RAG réinitialisé.
3 bis. Si simple échange de politesse ("bonjour", "merci", "au revoir",
   dans les 4 langues) → réponse toute prête, sans RAG ni LLM ; compteur
   de boucle RAG réinitialisé.
4. Sinon → recherche RAG dans la knowledge base (ChromaDB). Le compteur
   rag_attempts_count de la session compte les réponses du LLM qui
   disent ne pas avoir l'information ; à 3 échecs consécutifs, une
   escalade automatique remplace la 3e réponse plutôt que de laisser le
   client tourner en boucle. Une réponse informative, une escalade, une
   politesse ou un signal de satisfaction explicite ("merci, c'est
   réglé"...) réinitialise le compteur.
5. Si la recherche RAG aboutit mais avec une confiance trop faible
   (1 - distance du meilleur hit < RAG_CONFIDENCE_THRESHOLD, ou score
   reranker si RAG_CONFIDENCE_SIGNAL="reranker", voir
   retriever.get_confidence_threshold et config.py pour la calibration)
   → escalade immédiate, PAS d'appel
   LLM : mieux vaut transférer que risquer une hallucination sur un
   sujet mal couvert par la base de connaissances.
6. Sinon → appel au LLM (Groq) avec le contexte trouvé ET les derniers
   messages de la session (mémoire conversationnelle). Une question de
   suivi ("et la garantie ?") est aussi rattachée à la question
   précédente du client pour la recherche RAG (_build_retrieval_query).
7. Persistance de l'échange dans la session Redis (session_manager),
   puis dans PostgreSQL (conversation + messages) par une tâche de fond
   qui ne retarde pas la réponse (voir _persist_exchange).

Les appels bloquants (embeddings, requête ChromaDB, appel Groq) sont
exécutés dans un thread (asyncio.to_thread) pour ne pas bloquer la
boucle d'événements FastAPI pendant qu'ils tournent.
"""

import asyncio
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import settings
from app.db.database import AsyncSessionLocal
from app.db.repositories.conversation_repository import ConversationRepository
from app.db.repositories.user_repository import UserRepository
from app.services.language_detector import detect_language
from app.services.intent_classifier import Category, IntentClassifier
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

# Réponses aux échanges de politesse (voir intent_classifier, catégorie
# SMALL_TALK), par type et par langue. Le tunisien est en arabizi, comme
# les messages d'escalade.
SMALL_TALK_MESSAGES = {
    "greeting": {
        "fr": "Bonjour ! Je suis l'assistant Liss Strike. Je peux vous aider sur nos produits, la livraison, les retours ou la garantie. Que puis-je faire pour vous ?",
        "en": "Hello! I'm the Liss Strike assistant. I can help you with our products, delivery, returns or warranty. How can I help you?",
        "ar": "مرحباً! أنا المساعد الآلي لـ Liss Strike. يمكنني مساعدتك بخصوص منتجاتنا، التوصيل، الإرجاع أو الضمان. كيف يمكنني مساعدتك؟",
        "tn": "Aslema! Ena l'assistant mta3 Liss Strike. Najjem n3awnek fel produits, livraison, retour wala garantie. Chnowa t7eb?",
    },
    "thanks": {
        "fr": "Avec plaisir ! N'hésitez pas si vous avez une autre question.",
        "en": "You're welcome! Feel free to ask if you have any other question.",
        "ar": "على الرحب والسعة! لا تتردد إذا كان لديك سؤال آخر.",
        "tn": "Bel 3ani! Ken 3andek sou2el ekher, ahna houni.",
    },
    "goodbye": {
        "fr": "Au revoir et à bientôt chez Liss Strike !",
        "en": "Goodbye, see you soon at Liss Strike!",
        "ar": "إلى اللقاء، نراك قريباً في Liss Strike!",
        "tn": "Beslema, nchoufouk 9rib fi Liss Strike!",
    },
}


def _get_small_talk_message(kind: str, language: str) -> str:
    by_language = SMALL_TALK_MESSAGES.get(kind) or SMALL_TALK_MESSAGES["greeting"]
    return by_language.get(language, by_language["fr"])


# Nombre de réponses "je n'ai pas l'information" CONSÉCUTIVES au-delà
# duquel on force une escalade automatique — le bot n'arrive visiblement
# pas à aider, mieux vaut transférer que de laisser le client tourner en
# boucle. Une réponse informative ou un signal de satisfaction remet le
# compteur à zéro.
RAG_LOOP_THRESHOLD = 3

# Réponses du LLM où il dit ne pas avoir l'information (le prompt lui
# demande de le dire clairement plutôt que d'inventer, cf.
# llm_factory.BASE_SYSTEM_PROMPT). Formulations relevées sur de vraies
# réponses ; apostrophes typographiques normalisées avant la recherche.
# Limite : détection par mots-clés, une formulation inédite n'est pas
# comptée (le client peut toujours demander un humain explicitement).
_NO_INFO_PATTERNS = [re.compile(p, re.IGNORECASE) for p in (
    # Français
    r"je n'ai pas (cette |d'|l'|de |les? |la |aucune )?(information|info|donn[ée]e|d[ée]tail|pr[ée]cision)",
    r"je ne (dispose|trouve) pas",
    r"je n'ai pas acc[èe]s",
    r"aucune information",
    # Anglais
    r"i (don't|do not) have (\w+ ){0,4}(information|info|details|data)",  # "...the specific warranty details"
    r"i (couldn't|could not|can't|cannot) find",
    r"no information (about|on|regarding)",
    # Arabe
    r"(ليس|ليست) (لدي|لديّ|عندي)",
    r"لا (تتوفر|يتوفر|أملك|توجد) (لدي|لديّ )?معلومات",
    # Tunisien (lettres arabes et arabizi)
    r"ما ?عنديش",
    r"ma ?3andi?ch",
)]


def _is_no_info_answer(text: str) -> bool:
    normalized = text.replace("’", "'").replace("‘", "'")
    return any(p.search(normalized) for p in _NO_INFO_PATTERNS)


def _get_escalation_message(reason: Optional[str], language: str) -> str:
    """Message canned selon la raison d'escalade, avec repli sur
    "explicit"/fr si la raison ou la langue est inconnue."""
    by_language = ESCALATION_MESSAGES.get(reason) or ESCALATION_MESSAGES["explicit"]
    return by_language.get(language, by_language["fr"])


# ── Mémoire conversationnelle ──────────────────────────────────────────
# Nombre de messages précédents (user + assistant) renvoyés au LLM :
# 6 = les 3 derniers échanges, assez pour une question de suivi sans
# alourdir chaque appel Groq (voir llm_factory.build_messages).
HISTORY_MESSAGES_FOR_LLM = 6

# Détection d'une question de suivi, par règles volontairement étroites.
# Choix documenté : pas de reformulation par LLM (un appel Groq de plus
# par message, latence et quota) ; une règle simple suffit pour les
# suivis typiques d'un SAV. Et la règle doit rester ÉTROITE : testé,
# concaténer la question précédente à une question autonome ("frais de
# livraison ?" après "avez-vous l'Arduino Uno ?") fait disparaître la
# politique de livraison des résultats.
# 1) Connecteur en tête de message : "et la garantie ?", "and the price?",
#    "w el prix ?", "و الضمان" / "والضمان".
_FOLLOW_UP_CONNECTORS = {"et", "ou", "sinon", "aussi", "and", "or", "also", "w", "wel", "و"}
# 2) Pronom renvoyant à ce qui précède, dans une question courte
#    ("il coûte combien ?", "is it in stock?"). Limité aux questions
#    courtes : "est-ce qu'il y a une livraison express ?" est autonome.
_FOLLOW_UP_PRONOUNS = {
    "il", "elle", "ils", "elles", "ça", "ca", "celui", "celle", "ceux", "celles",
    "it", "its", "they", "them", "this", "that",
    "hedha", "hedhi", "hadha", "hadhi", "هذا", "هذه", "ذلك",
}
_FOLLOW_UP_MAX_WORDS = 6
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _is_follow_up(message: str) -> bool:
    """Vrai si le message n'a pas de sens sans la question précédente."""
    words = _WORD_RE.findall(message.lower())
    if not words:
        return False
    first = words[0]
    if first in _FOLLOW_UP_CONNECTORS or (first.startswith("وال") and len(first) > 3):
        return True
    return len(words) <= _FOLLOW_UP_MAX_WORDS and any(w in _FOLLOW_UP_PRONOUNS for w in words)


def _build_retrieval_query(message: str, previous_messages: list) -> str:
    """
    Requête envoyée au RAG. Pour une question de suivi, on la fait
    précéder de la dernière question AUTONOME du client (qui porte le
    sujet), en remontant au-delà des suivis successifs ("et la
    garantie ?" puis "et le prix ?" → toujours rattachés à "avez-vous
    l'Arduino Uno ?").

    Question précédente du CLIENT plutôt que dernière réponse du bot :
    testé sur "et la garantie ?" après l'Arduino Uno, la question du
    client retrouve la politique de garantie des cartes programmables
    ET les produits Arduino, alors que la réponse du bot (prix,
    variantes...) noie le sujet et fait perdre la politique de garantie.
    """
    if not _is_follow_up(message):
        return message
    for past in reversed(previous_messages):
        if past.get("role") == "user" and not _is_follow_up(past.get("content", "")):
            return f"{past['content']}\n{message}"
    return message


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
    # Conseiller aux commandes : aucune réponse du bot (response vide),
    # les canaux n'envoient rien au client.
    handled_by_agent: bool = False


# ── Persistance PostgreSQL ─────────────────────────────────────────────
# Redis garde la session vivante (1 h) ; PostgreSQL garde la trace de
# toutes les conversations (suivi SAV, statistiques). L'écriture se fait
# dans une tâche de fond, APRÈS le calcul de la réponse : elle n'ajoute
# aucune latence au client, et une panne de PostgreSQL n'empêche pas le
# chatbot de répondre (erreur journalisée seulement).
#
# Dernière tâche d'écriture par session : chaque échange attend la
# précédente, pour que les messages d'une même conversation soient
# écrits dans l'ordre et que la conversation ne soit créée qu'une fois.
_last_persist_task: dict = {}
_pending_persist_tasks: set = set()


def _alive_in_this_loop(task: asyncio.Task) -> bool:
    """Tâche encore en cours ET liée à la boucle courante. Une tâche d'une
    autre boucle (déjà fermée) ne se terminera jamais : l'attendre
    bloquerait indéfiniment. N'arrive pas en production (une seule
    boucle), mais sous pytest-asyncio chaque test a sa propre boucle."""
    return not task.done() and task.get_loop() is asyncio.get_running_loop()


async def _persist_exchange(previous: Optional[asyncio.Task], session_id: str, channel: str,
                            user_message: str, result: DialogueResult,
                            received_at: datetime, answered_at: datetime):
    if previous is not None and _alive_in_this_loop(previous):
        await asyncio.wait([previous])
    t0 = time.perf_counter()
    try:
        async with AsyncSessionLocal() as db:
            conversations = ConversationRepository(db)
            # external_id = identifiant de session du canal : numéro
            # WhatsApp, PSID Messenger, client_id WebSocket...
            user, _ = await UserRepository(db).get_or_create(session_id, channel)
            # Conversation en cours = dernière conversation active depuis
            # moins que la durée d'une session Redis ; sinon, nouvelle
            # conversation. Retrouvée en base plutôt que stockée dans la
            # session Redis : session_manager réécrit la session entière à
            # chaque message, une écriture depuis cette tâche de fond
            # pourrait écraser (ou être écrasée par) celle du message suivant.
            active_since = datetime.now(timezone.utc) - timedelta(seconds=_session_manager.SESSION_TTL)
            conv = await conversations.get_recent_for_user(user.id, active_since)
            if conv is None:
                conv = await conversations.create(user.id, channel)

            await conversations.add_message(
                conv.id, "user", user_message, {"language": result.language}, created_at=received_at,
            )
            if result.handled_by_agent:
                # Conseiller aux commandes : pas de réponse du bot à enregistrer
                await db.commit()
                return
            await conversations.add_message(
                conv.id, "assistant", result.response,
                {
                    "intent": result.intent,
                    "confidence": result.confidence,
                    "sources": [s for s in result.sources if s],
                    "escalated": result.escalated,
                    "escalation_reason": result.escalation_reason,
                },
                processing_time_ms=result.processing_time_ms,
                created_at=answered_at,
            )
            if result.escalated:
                conv.status = "escalated"
            await db.commit()
        logger.debug(f"🗄️ Échange persisté en {(time.perf_counter() - t0) * 1000:.0f}ms | session={session_id}")
    except Exception as e:
        logger.warning(f"⚠️ Persistance PostgreSQL échouée (réponse déjà envoyée) | session={session_id} : {e}")


def _schedule_persist(session_id: str, channel: str, user_message: str, result: DialogueResult,
                      received_at: datetime, answered_at: datetime):
    task = asyncio.create_task(_persist_exchange(
        _last_persist_task.get(session_id), session_id, channel, user_message, result,
        received_at, answered_at,
    ))
    _last_persist_task[session_id] = task
    _pending_persist_tasks.add(task)  # référence forte : évite qu'une tâche soit ramassée en cours

    def _done(t: asyncio.Task):
        _pending_persist_tasks.discard(t)
        if _last_persist_task.get(session_id) is t:
            del _last_persist_task[session_id]
    task.add_done_callback(_done)


async def wait_for_pending_persistence():
    """Attend la fin des écritures PostgreSQL en cours (tests, arrêt propre)."""
    pending = [t for t in _pending_persist_tasks if _alive_in_this_loop(t)]
    _pending_persist_tasks.difference_update(t for t in list(_pending_persist_tasks) if t not in pending)
    if pending:
        await asyncio.wait(pending)


async def handle_message(message: str, session_id: Optional[str] = None, channel: str = "web") -> DialogueResult:
    """
    Point d'entrée de tous les canaux : calcule la réponse, puis programme
    l'enregistrement de l'échange dans PostgreSQL (tâche de fond, quelle
    que soit l'issue : réponse RAG ou escalade).
    """
    session_id = session_id or str(uuid.uuid4())
    # Horodatages de l'échange, pris ici plutôt qu'en base : les deux
    # messages sont écrits dans la même transaction, où now() PostgreSQL
    # renvoie la même valeur (heure de début de la transaction).
    # Réponse au moins 1 µs après la réception : ordre strict garanti même
    # si l'horloge renvoie deux fois la même valeur.
    received_at = datetime.now(timezone.utc)
    if await agent_has_the_conversation(session_id, channel):
        result = await _handled_by_agent(message, session_id, channel)
    else:
        result = await _handle_message(message, session_id, channel)
    answered_at = max(datetime.now(timezone.utc), received_at + timedelta(microseconds=1))
    _schedule_persist(session_id, channel, message, result, received_at, answered_at)
    return result


# ── Prise en main par un conseiller ────────────────────────────────────
# Même durée que la session Redis : sans message du conseiller pendant ce
# délai, le bot reprend la main (le client n'attend pas indéfiniment).
AGENT_TAKEOVER_TIMEOUT = timedelta(seconds=_session_manager.SESSION_TTL)


async def agent_has_the_conversation(session_id: str, channel: str) -> bool:
    """
    True si un conseiller a pris la main sur la conversation en cours de ce
    client (statut "agent", posé par POST /admin/escalations/{id}/reply) et
    lui a écrit il y a moins d'AGENT_TAKEOVER_TIMEOUT. Passé ce délai, la
    conversation repasse "escalated" (toujours visible sur /admin) et le bot
    reprend la main.

    Lecture PostgreSQL synchrone, avant toute réponse : seule source de
    vérité du statut. En cas d'erreur (PostgreSQL indisponible), False :
    le bot répond comme avant plutôt que de laisser le client sans réponse.
    """
    try:
        async with AsyncSessionLocal() as db:
            user = await UserRepository(db).get_by_external_id(session_id, channel)
            if user is None:
                return False
            conversations = ConversationRepository(db)
            now = datetime.now(timezone.utc)
            conv = await conversations.get_recent_for_user(user.id, now - AGENT_TAKEOVER_TIMEOUT)
            if conv is None or conv.status != "agent":
                return False
            last_agent = await conversations.last_agent_message_at(conv.id)
            if last_agent is not None and last_agent >= now - AGENT_TAKEOVER_TIMEOUT:
                return True
            conv.status = "escalated"
            conv.context = {**(conv.context or {}), "agent_timeout_at": now.isoformat()}
            await db.commit()
            logger.info(f"⏱️ Prise en main expirée (aucun message du conseiller depuis 1 h), "
                        f"le bot reprend la main | session={session_id}")
            return False
    except Exception as e:
        logger.warning(f"⚠️ Statut de prise en main illisible, le bot répond | session={session_id} : {e}")
        return False


async def _handled_by_agent(message: str, session_id: str, channel: str) -> DialogueResult:
    """Conseiller aux commandes : le message reste dans l'historique
    (session Redis, puis PostgreSQL via la persistance), sans réponse."""
    start = time.time()
    await _session_manager.get_or_create(session_id, channel)
    await _session_manager.add_message(session_id, "user", message)
    logger.info(f"🧑‍💼 Conversation prise en main par un conseiller, pas de réponse du bot | session={session_id}")
    return DialogueResult(
        response="", session_id=session_id, language=detect_language(message),
        intent="handled_by_agent", confidence=0.0, escalated=False,
        processing_time_ms=int((time.time() - start) * 1000), handled_by_agent=True,
    )


async def record_agent_message(session_id: str, text: str) -> None:
    """Ajoute la réponse d'un conseiller à la session Redis du client : quand
    le bot reprend la main, sa mémoire conversationnelle en tient compte.
    Session expirée : rien à faire (le bot repartira d'une session neuve)."""
    try:
        await _session_manager.add_message(session_id, "assistant", text, {"agent": True})
    except Exception as e:
        logger.warning(f"⚠️ Message du conseiller non ajouté à la session Redis | session={session_id} : {e}")


async def _handle_message(message: str, session_id: str, channel: str) -> DialogueResult:
    start = time.time()

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

    # 4 bis. Échange de politesse seul ("bonjour", "merci", "au revoir"...)
    # → réponse toute prête, sans RAG ni LLM. Sans ça, la base ne contenant
    # aucune salutation, "bonjour" obtenait une confiance RAG sous le seuil
    # et déclenchait une escalade vers un humain. Le compteur de boucle RAG
    # est remis à zéro, comme le faisait cette escalade.
    if intent_result.category == Category.SMALL_TALK:
        language = intent_result.language_hint or language
        response_text = _get_small_talk_message(intent_result.intent, language)
        await _session_manager.reset_rag_attempts(session_id)
        await _session_manager.add_message(session_id, "assistant", response_text, {"intent": intent_result.intent})
        processing_time = int((time.time() - start) * 1000)
        logger.info(f"👋 Politesse ({intent_result.intent}) | session={session_id} | langue={language}")
        return DialogueResult(
            response=response_text, session_id=session_id, language=language,
            intent=intent_result.intent, confidence=intent_result.confidence,
            escalated=False, processing_time_ms=processing_time, sources=[],
        )

    # 5. Signal de satisfaction ("merci, c'est réglé"...) → le client
    # indique que son problème est résolu, on repart de zéro sur le
    # compteur de boucle avant de continuer normalement vers le RAG.
    # (6. Le compteur de boucle RAG n'est plus incrémenté ici, à chaque
    # question, mais après la réponse du LLM et seulement en cas d'échec
    # réel : voir étape 9 bis.)
    if _intent_classifier.is_satisfaction_signal(message):
        await _session_manager.reset_rag_attempts(session_id)

    # 7. RAG : recherche de contexte pertinent (bloquant → thread)
    # Pas de filtre par catégorie : retriever.search() sans type_filter
    # interroge déjà policy + product séparément puis fusionne (voir
    # retriever.py), ce qui couvre tous les cas sans distinction d'intent.
    # Mémoire : messages précédents de la session (le message courant,
    # déjà ajouté à l'étape 3, est retiré). Une question de suivi est
    # rattachée à la question précédente pour la recherche, et
    # l'historique récent est transmis au LLM (étape 9).
    previous_messages = (await _session_manager.get_history(session_id))[:-1]
    rag_query = _build_retrieval_query(message, previous_messages)
    if rag_query != message:
        logger.info(f"🧠 Question de suivi, requête RAG enrichie : {rag_query!r}")
    hits = await asyncio.to_thread(retriever.search, rag_query, 4)
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
    # ⚠️ Ce constat vaut pour le signal cosinus (défaut). Le score du
    # reranker (RAG_CONFIDENCE_SIGNAL="reranker", mode advanced) isole
    # ce 2e cas : 5 questions légitimes en arabe/tunisien dont le
    # meilleur chunk était faux passent sous son seuil — mais il n'est
    # pas activé par défaut, voir config.py (calibration étape 3).
    rag_confidence = retriever.get_best_confidence(hits)
    rag_threshold = retriever.get_confidence_threshold(hits)
    if rag_confidence < rag_threshold:
        response_text = _get_escalation_message("low_rag_confidence", language)
        await _session_manager.reset_rag_attempts(session_id)
        await _session_manager.add_message(
            session_id, "assistant", response_text,
            {"escalated": True, "escalation_reason": "low_rag_confidence", "rag_confidence": rag_confidence},
        )
        processing_time = int((time.time() - start) * 1000)
        logger.info(
            f"🚨 Escalade automatique (confiance RAG {rag_confidence:.3f} < "
            f"{rag_threshold}) | session={session_id} | langue={language}"
        )
        return DialogueResult(
            response=response_text, session_id=session_id, language=language,
            intent="low_rag_confidence", confidence=rag_confidence,
            escalated=True, processing_time_ms=processing_time, sources=[],
            escalation_reason="low_rag_confidence",
        )

    # 9. Appel LLM (bloquant → thread)
    response_text = await asyncio.to_thread(
        ask, message, language, context, previous_messages[-HISTORY_MESSAGES_FOR_LLM:],
    )

    # 9 bis. Compteur de boucle RAG : ne compte que les échecs RÉELS, où
    # le LLM dit ne pas avoir l'information (l'autre échec, la confiance
    # trop faible, escalade déjà immédiatement à l'étape 8). Une réponse
    # informative remet le compteur à zéro : il faut RAG_LOOP_THRESHOLD
    # échecs CONSÉCUTIFS pour transférer, à la place d'un énième "je ne
    # sais pas". Avant, chaque question RAG comptait, même bien répondue :
    # 3 bonnes questions d'affilée déclenchaient un transfert.
    if _is_no_info_answer(response_text):
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
                f"🚨 Escalade automatique (boucle RAG, {rag_attempts} échecs consécutifs) | "
                f"session={session_id} | langue={language}"
            )
            return DialogueResult(
                response=response_text, session_id=session_id, language=language,
                intent="repeated_rag_failure", confidence=1.0,
                escalated=True, processing_time_ms=processing_time, sources=[],
                escalation_reason="repeated_rag_failure",
            )
    else:
        await _session_manager.reset_rag_attempts(session_id)

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

    # confidence = confiance du RAG (celle comparée au seuil d'escalade à
    # l'étape 8), pas celle du classifieur d'intentions : sur une réponse
    # RAG, celle-ci vaut toujours 0.0 (aucune règle ne s'applique).
    return DialogueResult(
        response=response_text, session_id=session_id, language=language,
        intent=intent_result.intent, confidence=rag_confidence,
        escalated=False, processing_time_ms=processing_time, sources=sources,
    )
