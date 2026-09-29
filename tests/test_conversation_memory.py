# tests/test_conversation_memory.py
"""
Mémoire conversationnelle : détection des questions de suivi,
requête RAG enrichie, historique transmis au LLM.

Les tests de règles et de build_messages sont purs. Le test de
recherche nécessite ChromaDB peuplé ; le test de bout en bout
nécessite aussi une GROQ_API_KEY (2 appels LLM).
"""

import uuid

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.config import settings
from app.services.dialogue_manager import _build_retrieval_query, _is_follow_up, handle_message
from app.services.rag import retriever
from app.services.rag.llm_factory import HISTORY_MESSAGE_MAX_CHARS, build_messages
from tests.helpers import kb_indexed as _kb_indexed  # une seule vérification par exécution

ARDUINO_UNO_SKUS = {"LS-CP-000001", "LS-CP-000002"}  # Uno R3 original / clone


GROQ_KEY_MISSING = not settings.GROQ_API_KEY or settings.GROQ_API_KEY == "your_groq_api_key_here"
needs_kb = pytest.mark.skipif(not _kb_indexed(), reason="ChromaDB non peuplé")
needs_kb_and_groq = pytest.mark.skipif(
    GROQ_KEY_MISSING or not _kb_indexed(), reason="GROQ_API_KEY manquante ou ChromaDB non peuplé"
)

HISTORY = [
    {"role": "user", "content": "Avez-vous l'Arduino Uno ?"},
    {"role": "assistant", "content": "Oui, la carte Arduino Uno R3 est disponible : original à 63,18 DT, clone à 31,61 DT."},
]


def _sources(hits):
    return {h["metadata"].get("source") or h["metadata"].get("sku") for h in hits}


# --- Détection des questions de suivi (règles) ---

@pytest.mark.parametrize("message", [
    "et la garantie ?",
    "Et le prix ?",
    "and the warranty?",
    "w el prix ?",
    "والضمان؟",
    "il coûte combien ?",
    "is it in stock?",
])
def test_follow_up_detected(message):
    assert _is_follow_up(message)


@pytest.mark.parametrize("message", [
    "frais de livraison ?",                        # courte mais autonome
    "Avez-vous l'Arduino Uno ?",
    "Est-ce qu'il y a une livraison express le samedi ?",  # "il" mais question longue et autonome
    "ما هي مدة الضمان",                            # هي : pas un renvoi
    "",
])
def test_standalone_question_not_follow_up(message):
    assert not _is_follow_up(message)


def test_retrieval_query_prefixes_previous_user_question():
    assert _build_retrieval_query("et la garantie ?", HISTORY) == "Avez-vous l'Arduino Uno ?\net la garantie ?"


def test_retrieval_query_unchanged_for_standalone_question():
    assert _build_retrieval_query("frais de livraison ?", HISTORY) == "frais de livraison ?"


def test_retrieval_query_chains_successive_follow_ups_to_the_subject():
    history = HISTORY + [
        {"role": "user", "content": "et la garantie ?"},
        {"role": "assistant", "content": "6 mois contre les défauts de fabrication."},
    ]
    assert _build_retrieval_query("et le prix ?", history) == "Avez-vous l'Arduino Uno ?\net le prix ?"


def test_retrieval_query_without_history():
    assert _build_retrieval_query("et la garantie ?", []) == "et la garantie ?"


# --- Historique transmis au LLM ---

def test_build_messages_includes_history_between_system_and_current():
    messages = build_messages("et la garantie ?", "fr", "contexte", HISTORY)
    assert [type(m) for m in messages] == [SystemMessage, HumanMessage, AIMessage, HumanMessage]
    assert messages[1].content == "Avez-vous l'Arduino Uno ?"
    assert messages[-1].content == "et la garantie ?"


def test_build_messages_truncates_long_history_and_keeps_old_behaviour():
    long_history = [{"role": "assistant", "content": "x" * 5000}]
    assert len(build_messages("q", "fr", history=long_history)[1].content) == HISTORY_MESSAGE_MAX_CHARS
    # Sans historique : system + message courant, comme avant
    assert [type(m) for m in build_messages("q", "fr")] == [SystemMessage, HumanMessage]


# --- Recherche RAG sur le vrai corpus ---

@pytest.mark.integration
@needs_kb
def test_follow_up_warranty_question_finds_arduino_and_its_warranty():
    """ "et la garantie ?" après "Avez-vous l'Arduino Uno ?" doit retrouver
    l'Arduino Uno ET la garantie des cartes programmables ; seule, la
    question ne ramène que des politiques de garantie génériques."""
    alone = retriever.search("et la garantie ?", 4)
    assert not (_sources(alone) & ARDUINO_UNO_SKUS)

    hits = retriever.search(_build_retrieval_query("et la garantie ?", HISTORY), 4)
    assert _sources(hits) & ARDUINO_UNO_SKUS
    assert any("cartes programmables" in h["document"] and "garantie" in h["document"] for h in hits)


# --- Bout en bout (Groq) ---

@pytest.mark.integration
@needs_kb_and_groq
@pytest.mark.asyncio
async def test_handle_message_follow_up_keeps_the_subject():
    session_id = f"test-memory-{uuid.uuid4()}"
    await handle_message("Avez-vous l'Arduino Uno ?", session_id=session_id, channel="web")
    result = await handle_message("et la garantie ?", session_id=session_id, channel="web")

    assert result.escalated is False
    assert set(result.sources) & ARDUINO_UNO_SKUS
    assert "sav/garantie.txt" in result.sources
    # Garantie des cartes programmables. split() normalise les espaces :
    # le LLM écrit souvent "6 mois" (espace fine insécable).
    assert "6 mois" in " ".join(result.response.split())
