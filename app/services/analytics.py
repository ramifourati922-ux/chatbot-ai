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
- build_stats() calcule les indicateurs : fonction pure, testée sans base.
Les messages de la période sont chargés en mémoire : adapté au volume
d'une petite boutique (quelques milliers de messages par mois). Au-delà,
il faudrait agréger directement en SQL.
"""

import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional
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
    by_conversation = defaultdict(list)
    for m in messages:
        by_conversation[m.conversation_id].append(m)
    unanswered = {}
    no_info_answers = 0
    for conv_messages in by_conversation.values():
        conv_messages.sort(key=lambda m: m.created_at)
        last_question = None
        for m in conv_messages:
            if m.role == "user":
                last_question = m
                continue
            if m.role != "assistant" or last_question is None:
                continue
            reason = m.metadata.get("escalation_reason")
            if reason in UNANSWERED_REASONS:
                kind = "reponse_non_trouvee" if reason == "low_rag_confidence" else "echecs_repetes"
            elif reply_type(m.metadata) == "rag" and _is_no_info_answer(m.content):
                kind = "sans_information"
                no_info_answers += 1
            else:
                continue
            key = normalize_question(last_question.content)
            if not key:
                continue
            item = unanswered.setdefault(key, {
                "question": last_question.content, "occurrences": 0, "last_asked_at": last_question.created_at,
                "language": last_question.metadata.get("language"), "channels": set(), "reasons": set(),
            })
            item["occurrences"] += 1
            if last_question.created_at >= item["last_asked_at"]:
                item["last_asked_at"] = last_question.created_at
                item["question"] = last_question.content  # formulation la plus récente
            item["channels"].add(m.channel)
            item["reasons"].add(kind)
            last_question = None  # une question ne compte qu'une fois
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
                           metadata=r[5] or {}, processing_time_ms=r[6], created_at=r[7]) for r in msg_rows]
    return conversations, messages


async def compute_stats(db: AsyncSession, days: int, now: Optional[datetime] = None) -> dict:
    until = now or datetime.now(timezone.utc)
    since = until - timedelta(days=days)
    conversations, messages = await load_period(db, since)
    return build_stats(conversations, messages, since, until)
