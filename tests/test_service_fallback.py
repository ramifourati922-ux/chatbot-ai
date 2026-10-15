# tests/test_service_fallback.py
"""
Pannes de la recherche (ChromaDB) ou du LLM (Groq, modèle principal et
secours) : le client reçoit un message d'excuse dans sa langue et la
conversation passe aux conseillers (raison "service_unavailable"), au lieu
d'une erreur 500 sur le site ou d'un silence sur WhatsApp.

Et temps de chaque étape d'une réponse RAG (recherche, LLM), mesurés et
repris par les statistiques.

Session en mémoire, recherche et LLM remplacés : ni Redis, ni ChromaDB,
ni Groq.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.services import analytics, dialogue_manager
from app.services.analytics import MessageRow
from app.services.session_manager import SessionManager

PASSAGE = {"document": "Q: délai ?\nR: 2 à 4 jours.", "metadata": {"source": "sav/livraison.txt"}, "distance": 0.2}


@pytest.fixture
def engine(monkeypatch):
    sessions = SessionManager()
    sessions._redis_available = False
    monkeypatch.setattr(dialogue_manager, "_session_manager", sessions)
    monkeypatch.setattr(dialogue_manager.retriever, "search", lambda query, top_k=4, type_filter=None: [PASSAGE])
    monkeypatch.setattr(dialogue_manager, "ask", lambda *args, **kwargs: "Le délai est de 2 à 4 jours.")
    return monkeypatch


def _broken(*args, **kwargs):
    raise ConnectionError("service injoignable")


@pytest.mark.asyncio
@pytest.mark.parametrize("language, message", [
    ("fr", "Quel est le délai de livraison ?"),
    ("en", "What are the delivery times?"),
])
async def test_search_failure_transfers_the_client(engine, language, message):
    engine.setattr(dialogue_manager.retriever, "search", _broken)
    result = await dialogue_manager._handle_message(message, f"test-fallback-search-{language}", "web")
    assert result.escalated and result.escalation_reason == "service_unavailable"
    assert result.response == dialogue_manager.ESCALATION_MESSAGES["service_unavailable"][language]


@pytest.mark.asyncio
async def test_llm_failure_transfers_the_client(engine):
    engine.setattr(dialogue_manager, "ask", _broken)
    result = await dialogue_manager._handle_message("Quel est le délai de livraison ?", "test-fallback-llm", "web")
    assert result.escalated and result.escalation_reason == "service_unavailable"


def test_service_unavailable_message_exists_in_every_language():
    assert set(dialogue_manager.ESCALATION_MESSAGES["service_unavailable"]) == {"fr", "en", "ar", "tn"}


@pytest.mark.asyncio
async def test_rag_answer_records_the_time_of_each_step(engine):
    result = await dialogue_manager._handle_message("Quel est le délai de livraison ?", "test-fallback-ok", "web")
    assert not result.escalated
    assert set(result.timings) == {"retrieval_ms", "llm_ms"}
    assert all(isinstance(v, int) and v >= 0 for v in result.timings.values())


def test_statistics_report_search_and_llm_times():
    t0 = datetime(2026, 10, 1, 10, tzinfo=timezone.utc)
    rows = [
        MessageRow("c1", "web", "user", "délai ?", {"language": "fr"}, None, t0),
        MessageRow("c1", "web", "assistant", "2 à 4 jours", {"intent": "general", "retrieval_ms": 300, "llm_ms": 1700},
                   2050, t0 + timedelta(seconds=2)),
        MessageRow("c1", "web", "user", "garantie ?", {"language": "fr"}, None, t0 + timedelta(seconds=10)),
        MessageRow("c1", "web", "assistant", "2 ans", {"intent": "general", "retrieval_ms": 500, "llm_ms": 2100},
                   2650, t0 + timedelta(seconds=13)),
        MessageRow("c1", "web", "assistant", "Bonjour !", {"intent": "greeting"}, 12, t0 + timedelta(seconds=20)),
    ]
    stats = analytics.build_stats([analytics.ConversationRow("c1", "web", "active")], rows,
                                  t0 - timedelta(days=1), t0 + timedelta(days=1))
    assert stats["latency"]["recherche"]["median_ms"] == 400
    assert stats["latency"]["llm"]["median_ms"] == 1900
    assert stats["latency"]["sans_llm"]["count"] == 1  # la politesse n'entre pas dans le détail RAG
