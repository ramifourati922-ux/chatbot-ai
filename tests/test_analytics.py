# tests/test_analytics.py
"""
Statistiques du tableau de bord (app/services/analytics.py, /admin/stats).

- build_stats est une fonction pure : testée sur des conversations et
  messages construits à la main, sans base ;
- un test d'intégration vérifie la route /admin/stats sur la vraie base
  (échanges réels via handle_message, sans appel au LLM : transfert
  explicite et politesse).
"""

import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import delete

from app.services.analytics import (
    ConversationRow, MessageRow, build_stats, normalize_question, real_channel, reply_type,
)

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
SINCE = NOW - timedelta(days=7)


def conv(cid, channel="web", status="active"):
    return ConversationRow(id=cid, channel=channel, status=status)


def msg(cid, role, content="", minutes=0, channel="web", ms=None, **metadata):
    return MessageRow(conversation_id=cid, channel=channel, role=role, content=content, metadata=metadata,
                      processing_time_ms=ms, created_at=NOW - timedelta(days=1) + timedelta(minutes=minutes))


def stats(conversations, messages, **kwargs):
    return build_stats(conversations, messages, SINCE, NOW, **kwargs)


# ── Taux d'automatisation ───────────────────────────────────────────────

def test_automation_rate_counts_conversations_never_transferred():
    conversations = [conv("a"), conv("b"), conv("c")]
    messages = [
        msg("a", "user", "Bonjour", 0, language="fr"), msg("a", "assistant", "Bonjour !", 1, intent="greeting"),
        msg("b", "user", "Frais de livraison ?", 0, language="fr"),
        msg("b", "assistant", "7 DT.", 1, intent="general", ms=1500),
        msg("c", "user", "Je veux un humain", 0, language="fr"),
        msg("c", "assistant", "Je vous mets en relation.", 1, intent="human_agent",
            escalated=True, escalation_reason="explicit", ms=12),
    ]
    c = stats(conversations, messages)["conversations"]
    assert (c["total"], c["automated"], c["escalated"]) == (3, 2, 1)
    assert c["automation_rate"] == pytest.approx(0.667, abs=0.001)


def test_conversation_taken_over_counts_as_transferred_even_without_message_in_period():
    """Transférée avant la période (message hors période), prise en main pendant."""
    s = stats([conv("a", status="agent"), conv("b", status="resolved"), conv("c")], [])
    assert s["conversations"]["escalated"] == 2
    assert s["conversations"]["resolved_by_agents"] == 1


def test_empty_period_has_no_rate_and_zero_days():
    s = stats([], [])
    assert s["conversations"]["automation_rate"] is None
    assert len(s["daily"]) == 8  # 7 jours + aujourd'hui
    assert all(d["client_messages"] == 0 and d["transfers"] == 0 for d in s["daily"])


# ── Réponses, transferts, langues, canaux ───────────────────────────────

@pytest.mark.parametrize("metadata,expected", [
    ({"intent": "general"}, "rag"),
    ({"intent": "greeting"}, "politesse"),
    ({"intent": "thanks"}, "politesse"),
    ({"intent": "order_tracking"}, "suivi_commande"),
    ({"intent": "order_tracking", "escalated": True, "escalation_reason": "order_tracking"}, "transfert"),
    ({"intent": "low_rag_confidence", "escalated": True}, "transfert"),
])
def test_reply_type(metadata, expected):
    assert reply_type(metadata) == expected


def test_replies_transfers_languages_and_channels():
    conversations = [conv("w"), conv("wa", "whatsapp")]
    messages = [
        msg("w", "user", "salut", 0, language="fr"), msg("w", "assistant", "Bonjour !", 1, intent="greeting"),
        msg("wa", "user", "nheb na7ki m3a agent", 0, "whatsapp", language="tn"),
        msg("wa", "assistant", "...", 1, "whatsapp", intent="human_agent", escalated=True, escalation_reason="explicit"),
        msg("wa", "agent", "Bonjour, je suis Sami.", 5, "whatsapp"),
    ]
    s = stats(conversations, messages)
    assert s["replies_by_type"] == {"politesse": 1, "transfert": 1}
    assert s["transfers_by_reason"] == {"explicit": 1}
    assert s["by_language"] == {"fr": 1, "tn": 1}
    assert s["by_channel"]["whatsapp"] == {"conversations": 1, "client_messages": 1, "transfers": 1}
    assert s["agent_replies"] == 1


def test_web_session_is_always_the_web_channel():
    """POST /chat/ accepte channel="whatsapp" : l'identifiant web: prime."""
    assert real_channel("whatsapp", "web:abc") == "web"
    assert real_channel("whatsapp", "21600000099") == "whatsapp"


def test_latency_separates_rag_from_answers_without_llm():
    messages = [msg("a", "assistant", "r", i, intent="general", ms=ms) for i, ms in enumerate([1000, 1200, 1900])]
    messages += [msg("a", "assistant", "b", 10, intent="greeting", ms=8),
                 msg("a", "assistant", "t", 11, intent="human_agent", escalated=True, escalation_reason="explicit", ms=20)]
    latency = stats([conv("a")], messages)["latency"]
    assert latency["rag"] == {"median_ms": 1200, "p90_ms": 1900, "count": 3}
    assert latency["sans_llm"]["median_ms"] == 14 and latency["sans_llm"]["count"] == 2


def test_days_are_counted_in_tunis_time():
    """23h30 UTC = 00h30 à Tunis : le message compte pour le lendemain."""
    late = MessageRow("a", "web", "user", "?", {"language": "fr"}, None, datetime(2026, 9, 30, 23, 30, tzinfo=timezone.utc))
    daily = {d["date"].isoformat(): d["client_messages"] for d in stats([conv("a")], [late])["daily"]}
    assert daily["2026-10-01"] == 1 and daily["2026-09-30"] == 0


# ── Questions sans réponse ──────────────────────────────────────────────

def test_unanswered_questions_are_grouped_and_ranked():
    conversations = [conv("a"), conv("b"), conv("c", "messenger"), conv("d")]
    messages = [
        # Transfert « réponse non trouvée », deux formulations de la même question
        msg("a", "user", "Avez-vous l'Arduino Due ?", 0, language="fr"),
        msg("a", "assistant", "Je transfère.", 1, intent="low_rag_confidence", escalated=True,
            escalation_reason="low_rag_confidence"),
        msg("c", "user", "avez vous l arduino due", 0, "messenger", language="fr"),
        msg("c", "assistant", "Je transfère.", 1, "messenger", intent="low_rag_confidence", escalated=True,
            escalation_reason="low_rag_confidence"),
        # Réponse RAG « je n'ai pas l'information »
        msg("b", "user", "Livrez-vous à Sfax ?", 0, language="fr"),
        msg("b", "assistant", "Je n'ai pas l'information sur Sfax.", 1, intent="general"),
        # Question bien répondue : n'apparaît pas
        msg("d", "user", "Frais de livraison ?", 0, language="fr"),
        msg("d", "assistant", "La livraison coûte 7 DT.", 1, intent="general"),
    ]
    s = stats(conversations, messages)
    questions = s["unanswered_questions"]
    assert [q["occurrences"] for q in questions] == [2, 1]
    assert questions[0]["channels"] == ["messenger", "web"]
    assert questions[0]["reasons"] == ["reponse_non_trouvee"]
    assert questions[1]["question"] == "Livrez-vous à Sfax ?"
    assert questions[1]["reasons"] == ["sans_information"]
    assert s["rag_no_info_answers"] == 1


def test_explicit_request_or_small_talk_is_not_an_unanswered_question():
    messages = [
        msg("a", "user", "Je veux un humain", 0, language="fr"),
        msg("a", "assistant", "...", 1, intent="human_agent", escalated=True, escalation_reason="explicit"),
        msg("a", "user", "merci", 2, language="fr"),
        msg("a", "assistant", "Avec plaisir !", 3, intent="thanks"),
    ]
    assert stats([conv("a")], messages)["unanswered_questions"] == []


def test_normalize_question_ignores_case_accents_and_punctuation():
    assert normalize_question("Où est   ma COMMANDE ?!") == normalize_question("ou est ma commande")


# ── Route /admin/stats (base réelle) ────────────────────────────────────

@pytest.mark.asyncio
async def test_stats_route_counts_real_exchanges(agent_accounts):
    from app.db import database
    from app.main import app
    from app.models import User
    from app.services import dialogue_manager
    from app.services.dialogue_manager import handle_message, wait_for_pending_persistence

    session = f"test-stats-{uuid.uuid4()}"
    sessions = dialogue_manager._session_manager
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        auth = agent_accounts.conseiller.auth
        assert (await client.get("/admin/stats")).status_code == 401  # réservé aux conseillers
        assert (await client.get("/admin/statistiques", auth=auth)).status_code == 200
        before = (await client.get("/admin/stats?days=1", auth=auth)).json()
        try:
            await handle_message("Bonjour", session_id=session, channel="whatsapp")
            await handle_message("Je veux parler à un agent humain", session_id=session, channel="whatsapp")
            await wait_for_pending_persistence()
            after = (await client.get("/admin/stats?days=1", auth=auth)).json()
        finally:
            await sessions.delete_session(session)
            async with database.AsyncSessionLocal() as db:
                await db.execute(delete(User).where(User.external_id == session))
                await db.commit()
            await database.engine.dispose(close=False)

    assert after["conversations"]["total"] == before["conversations"]["total"] + 1
    assert after["conversations"]["escalated"] == before["conversations"]["escalated"] + 1
    assert after["client_messages"] == before["client_messages"] + 2
    assert after["transfers_by_reason"].get("explicit", 0) == before["transfers_by_reason"].get("explicit", 0) + 1
    assert after["replies_by_type"].get("politesse", 0) == before["replies_by_type"].get("politesse", 0) + 1
    assert len(after["daily"]) == 2
