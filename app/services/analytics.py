# app/services/analytics.py
"""
Statistiques du tableau de bord (/admin/statistiques) : mesure de ce que
le bot traite seul, de ce qu'il transfère, et des questions auxquelles il
ne sait pas répondre (à ajouter à la base de connaissances).

Tout est calculé à partir de ce qui est déjà enregistré pour chaque
échange (dialogue_manager._persist_exchange) : langue du message client ;
intention, transfert et sa raison, temps de traitement de chaque réponse.

Deux temps :
- load_period() lit en base les conversations et messages de la période ;
- build_stats() et build_leads() calculent les indicateurs et les
  prospects : fonctions pures, testées sans base.

Prospects (leads) : clients qui se sont renseignés sur un produit. Ils
sont déduits de l'historique (sources des réponses RAG = références
produits), sans table supplémentaire : rien n'est à saisir, et
l'historique enregistré reste la seule source de vérité.
Les messages de la période sont chargés en mémoire : adapté au volume
d'une petite boutique (quelques milliers de messages par mois). Au-delà,
il faudrait agréger directement en SQL.
"""

import csv
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Iterator, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.web_session import WEB_SESSION_PREFIX
from app.services.dialogue_manager import _is_no_info_answer

# Jours comptés à l'heure de la boutique, pas en UTC
TIMEZONE = ZoneInfo("Africa/Tunis")

SMALL_TALK_INTENTS = {"greeting", "thanks", "goodbye"}
# Transferts dus à une question à laquelle le bot n'a pas trouvé de réponse
UNANSWERED_REASONS = {"low_rag_confidence", "repeated_rag_failure"}
CONVERSATION_ESCALATED_STATUSES = {"escalated", "agent", "resolved"}

PRODUCTS_CSV = Path(__file__).resolve().parents[2] / "data" / "knowledge_base" / "ecommerce" / "produits.csv"
# Référence produit dans les sources d'une réponse RAG (les politiques ont
# pour source un chemin de fichier, ex. "sav/garantie.txt")
SKU_RE = re.compile(r"^LS-[A-Z]{2}-\d{6}$")
# Intention d'achat, dans les 4 langues : prix, disponibilité, achat
PURCHASE_INTENT_RE = re.compile(
    r"\b(prix|tarif|co[uû]te?|combien|disponib\w*|en stock|stock|acheter|achat|commander|"
    r"price|cost|how much|available|availability|in stock|buy|purchase|"
    r"9adeh|b9adeh|b9adech|9adech|soumou|famma|3andkom|3andek|nechri|nchri)\b"
    r"|سعر|بكم|ثمن|متوفر|متاح|شراء|نشري|عندكم|قداش|بقداش",
    re.IGNORECASE,
)
# Canaux où le client peut être recontacté après coup (le chat du site,
# seulement tant que son onglet est ouvert)
RECONTACTABLE_CHANNELS = {"whatsapp", "messenger"}


@dataclass
class ConversationRow:
    id: str
    channel: str  # canal réel (une session "web:" est toujours le site)
    status: str


@dataclass
class MessageRow:
    conversation_id: str
    channel: str  # canal réel de sa conversation
    role: str  # user | assistant | agent
    content: str
    metadata: dict
    processing_time_ms: Optional[int]
    created_at: datetime
    customer_id: Optional[str] = None  # n° WhatsApp, PSID Messenger, session web


def real_channel(channel: str, external_id: Optional[str]) -> str:
    return "web" if external_id and external_id.startswith(WEB_SESSION_PREFIX) else channel


def reply_type(metadata: dict) -> str:
    """Type de réponse du bot : transfert, politesse, suivi de commande ou RAG."""
    if metadata.get("escalated"):
        return "transfert"
    intent = metadata.get("intent")
    if intent in SMALL_TALK_INTENTS:
        return "politesse"
    if intent == "order_tracking":
        return "suivi_commande"
    return "rag"


def normalize_question(question: str) -> str:
    """Regroupe les variantes d'une même question : casse, accents,
    ponctuation et espaces ignorés."""
    text_ = unicodedata.normalize("NFKD", question.lower())
    text_ = "".join(c for c in text_ if not unicodedata.combining(c))
    return " ".join(re.findall(r"\w+", text_))


def question_reply_pairs(messages: list) -> Iterator[tuple]:
    """(question du client, réponse du bot) : chaque réponse du bot est
    associée au dernier message du client qui la précède dans la même
    conversation, une seule fois."""
    by_conversation = defaultdict(list)
    for m in messages:
        by_conversation[m.conversation_id].append(m)
    for conv_messages in by_conversation.values():
        conv_messages.sort(key=lambda m: m.created_at)
        last_question = None
        for m in conv_messages:
            if m.role == "user":
                last_question = m
            elif m.role == "assistant" and last_question is not None:
                yield last_question, m
                last_question = None


def _latency(values: list) -> Optional[dict]:
    if not values:
        return None
    ordered = sorted(values)
    p90 = ordered[min(len(ordered) - 1, int(round(0.9 * (len(ordered) - 1))))]
    return {"median_ms": int(statistics.median(ordered)), "p90_ms": int(p90), "count": len(ordered)}


def build_stats(conversations: list, messages: list, since: datetime, until: datetime,
                unanswered_limit: int = 20) -> dict:
    """Indicateurs de la période [since, until] (fonction pure)."""
    period_ids = {c.id for c in conversations}

    # ── Conversations : traitées seules ou transférées ──
    escalated_ids = {m.conversation_id for m in messages if m.role == "assistant" and m.metadata.get("escalated")}
    escalated_ids |= {c.id for c in conversations if c.status in CONVERSATION_ESCALATED_STATUSES}
    total = len(conversations)
    escalated = len(escalated_ids & period_ids)
    automated = total - escalated

    # ── Messages et réponses ──
    client_messages = [m for m in messages if m.role == "user"]
    replies = [m for m in messages if m.role == "assistant"]
    by_language = Counter(m.metadata.get("language") or "inconnue" for m in client_messages)
    replies_by_type = Counter(reply_type(m.metadata) for m in replies)
    transfers_by_reason = Counter(m.metadata.get("escalation_reason") or "inconnue"
                                  for m in replies if m.metadata.get("escalated"))

    by_channel = defaultdict(lambda: {"conversations": 0, "client_messages": 0, "transfers": 0})
    for c in conversations:
        by_channel[c.channel]["conversations"] += 1
    for m in client_messages:
        by_channel[m.channel]["client_messages"] += 1
    for m in replies:
        if m.metadata.get("escalated"):
            by_channel[m.channel]["transfers"] += 1

    # ── Temps de réponse : RAG (appel au LLM) ou sans LLM ──
    rag_times, fast_times = [], []
    for m in replies:
        if m.processing_time_ms is None:
            continue
        kind = reply_type(m.metadata)
        uses_llm = kind == "rag" or m.metadata.get("escalation_reason") == "repeated_rag_failure"
        (rag_times if uses_llm else fast_times).append(m.processing_time_ms)

    # ── Activité par jour (heure de Tunis), jours sans message compris ──
    daily = defaultdict(lambda: {"client_messages": 0, "transfers": 0})
    for m in client_messages:
        daily[m.created_at.astimezone(TIMEZONE).date()]["client_messages"] += 1
    for m in replies:
        if m.metadata.get("escalated"):
            daily[m.created_at.astimezone(TIMEZONE).date()]["transfers"] += 1
    first_day, last_day = since.astimezone(TIMEZONE).date(), until.astimezone(TIMEZONE).date()
    days = [first_day + timedelta(days=i) for i in range((last_day - first_day).days + 1)]

    # ── Questions sans réponse : la question du client qui précède un
    # transfert « réponse non trouvée » ou une réponse RAG « je n'ai pas
    # l'information » ──
    unanswered = {}
    no_info_answers = 0
    for question, reply in question_reply_pairs(messages):
        reason = reply.metadata.get("escalation_reason")
        if reason in UNANSWERED_REASONS:
            kind = "reponse_non_trouvee" if reason == "low_rag_confidence" else "echecs_repetes"
        elif reply_type(reply.metadata) == "rag" and _is_no_info_answer(reply.content):
            kind = "sans_information"
            no_info_answers += 1
        else:
            continue
        key = normalize_question(question.content)
        if not key:
            continue
        item = unanswered.setdefault(key, {
            "question": question.content, "occurrences": 0, "last_asked_at": question.created_at,
            "language": question.metadata.get("language"), "channels": set(), "reasons": set(),
        })
        item["occurrences"] += 1
        if question.created_at >= item["last_asked_at"]:
            item["last_asked_at"] = question.created_at
            item["question"] = question.content  # formulation la plus récente
        item["channels"].add(reply.channel)
        item["reasons"].add(kind)
    top_unanswered = sorted(unanswered.values(), key=lambda i: (-i["occurrences"], -i["last_asked_at"].timestamp()))

    return {
        "since": since,
        "until": until,
        "conversations": {
            "total": total,
            "automated": automated,
            "escalated": escalated,
            "automation_rate": round(automated / total, 3) if total else None,
            "resolved_by_agents": sum(1 for c in conversations if c.status == "resolved"),
        },
        "client_messages": len(client_messages),
        "agent_replies": sum(1 for m in messages if m.role == "agent"),
        "by_channel": dict(by_channel),
        "by_language": dict(by_language),
        "replies_by_type": dict(replies_by_type),
        "transfers_by_reason": dict(transfers_by_reason),
        "latency": {"rag": _latency(rag_times), "sans_llm": _latency(fast_times)},
        "daily": [{"date": d, **daily[d]} for d in days],
        "rag_no_info_answers": no_info_answers,
        "unanswered_questions": [
            {**item, "channels": sorted(item["channels"]), "reasons": sorted(item["reasons"])}
            for item in top_unanswered[:unanswered_limit]
        ],
    }


@lru_cache(maxsize=1)
def product_catalog() -> dict:
    """Référence produit -> nom, catégorie, prix (catalogue indexé dans le RAG)."""
    with open(PRODUCTS_CSV, encoding="utf-8") as f:
        return {row["sku"]: {"name": row["nom"], "category": row["categorie"], "price_dt": float(row["prix_dt"])}
                for row in csv.DictReader(f)}


def build_leads(messages: list, catalog: dict, limit: int = 50) -> list:
    """
    Prospects : clients qui se sont renseignés sur un produit (fonction pure).

    Une question compte si la réponse RAG s'appuie sur une fiche produit en
    première source (la question portait sur ce produit), ou si elle
    exprime une intention d'achat (prix, disponibilité, achat) et que la
    réponse cite des produits. Les produits d'intérêt sont les deux
    premières sources produit de chaque réponse, les plus fréquents d'abord.
    """
    leads = {}
    for question, reply in question_reply_pairs(messages):
        if reply_type(reply.metadata) != "rag" or not question.customer_id:
            continue
        sources = reply.metadata.get("sources") or []
        skus = [s for s in sources if isinstance(s, str) and SKU_RE.match(s) and s in catalog]
        if not skus:
            continue
        intent = bool(PURCHASE_INTENT_RE.search(question.content))
        if not intent and sources[0] != skus[0]:
            continue  # question sur une politique, qui a seulement fait remonter des produits
        lead = leads.setdefault(question.customer_id, {
            "customer_id": question.customer_id, "channel": reply.channel,
            "recontactable": reply.channel in RECONTACTABLE_CHANNELS,
            "language": question.metadata.get("language"),
            "first_seen": question.created_at, "last_seen": question.created_at,
            "product_questions": 0, "purchase_intent": False, "last_question": question.content,
            "_products": Counter(),
        })
        lead["product_questions"] += 1
        lead["purchase_intent"] = lead["purchase_intent"] or intent
        lead["first_seen"] = min(lead["first_seen"], question.created_at)
        if question.created_at >= lead["last_seen"]:
            lead["last_seen"] = question.created_at
            lead["last_question"] = question.content
        lead["_products"].update(skus[:2])  # au-delà, souvent des produits voisins sans rapport
    # Intention d'achat d'abord, puis les plus récents
    ranked = sorted(leads.values(), key=lambda lead: (not lead["purchase_intent"], -lead["last_seen"].timestamp()))
    result = []
    for lead in ranked[:limit]:
        products = [{"sku": sku, **catalog[sku]} for sku, _ in lead.pop("_products").most_common(3)]
        result.append({**lead, "products": products})
    return result


async def load_period(db: AsyncSession, since: datetime) -> tuple:
    """Conversations commencées et messages écrits depuis `since`."""
    conv_rows = await db.execute(text("""
        SELECT c.id::text, c.channel, c.status, u.external_id
        FROM conversations c JOIN users u ON u.id = c.user_id
        WHERE c.started_at >= :since
    """), {"since": since})
    conversations = [ConversationRow(id=r[0], channel=real_channel(r[1], r[3]), status=r[2]) for r in conv_rows]

    # Messages de la période, y compris ceux d'une conversation commencée
    # avant (comptés dans les volumes, pas dans le total des conversations).
    msg_rows = await db.execute(text("""
        SELECT m.conversation_id::text, c.channel, u.external_id, m.role, m.content, m.metadata,
               m.processing_time_ms, m.created_at
        FROM messages m
        JOIN conversations c ON c.id = m.conversation_id
        JOIN users u ON u.id = c.user_id
        WHERE m.created_at >= :since
    """), {"since": since})
    messages = [MessageRow(conversation_id=r[0], channel=real_channel(r[1], r[2]), role=r[3], content=r[4],
                           metadata=r[5] or {}, processing_time_ms=r[6], created_at=r[7], customer_id=r[2])
                for r in msg_rows]
    return conversations, messages


async def compute_stats(db: AsyncSession, days: int, now: Optional[datetime] = None) -> dict:
    until = now or datetime.now(timezone.utc)
    since = until - timedelta(days=days)
    conversations, messages = await load_period(db, since)
    stats = build_stats(conversations, messages, since, until)
    leads = build_leads(messages, product_catalog(), limit=len(messages) or 1)
    stats["leads"] = {
        "total": len(leads),
        "purchase_intent": sum(1 for lead in leads if lead["purchase_intent"]),
        "recontactable": sum(1 for lead in leads if lead["recontactable"]),
    }
    return stats


async def compute_leads(db: AsyncSession, days: int, limit: int = 50) -> list:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    _, messages = await load_period(db, since)
    return build_leads(messages, product_catalog(), limit=limit)
