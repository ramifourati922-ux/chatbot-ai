# tests/test_arabizi.py
"""
Expansion des questions en arabizi tunisien avant la recherche RAG
(app/services/arabizi.py, interrupteur RAG_ARABIZI_EXPANSION).

Unitaires : traduction ajoutée sans toucher à la question ; appliquée
seulement au tunisien ; la recherche reçoit la version complétée, le LLM
la question d'origine.
Intégration (ChromaDB) : la recherche reste au niveau mesuré dans
docs/evaluation/recherche_par_langue.md.
"""

import pytest

from app.config import settings
from app.services import arabizi, dialogue_manager
from app.services.session_manager import SessionManager


def test_expansion_keeps_the_question_and_adds_the_translation():
    assert arabizi.expand("kifech nraja3 produit ?") == "kifech nraja3 produit ? (comment retourner retour)"


def test_expansion_handles_several_spellings():
    assert "payer" in arabizi.expand("najjem nkhalles b carta ?")
    assert "payer" in arabizi.expand("najjem nkhallas b carta ?")


def test_question_without_known_word_is_unchanged():
    assert arabizi.expand("aslema labes") == "aslema labes"


@pytest.fixture
def captured(monkeypatch):
    sessions = SessionManager()
    sessions._redis_available = False
    monkeypatch.setattr(dialogue_manager, "_session_manager", sessions)
    calls = {"search": [], "llm": []}

    def search(query, top_k=4, type_filter=None):
        calls["search"].append(query)
        return [{"document": "Q: retour ?\nR: 7 jours.", "metadata": {"source": "sav/retours.txt"}, "distance": 0.2}]

    def ask(message, *args, **kwargs):
        calls["llm"].append(message)
        return "7 jours."

    monkeypatch.setattr(dialogue_manager.retriever, "search", search)
    monkeypatch.setattr(dialogue_manager, "ask", ask)
    return calls


@pytest.mark.asyncio
async def test_tunisian_question_is_expanded_for_the_search_only(captured, monkeypatch):
    monkeypatch.setattr(settings, "RAG_ARABIZI_EXPANSION", True)
    await dialogue_manager._handle_message("kifech nraja3 produit ?", "test-arabizi-on", "web")
    assert captured["search"] == ["kifech nraja3 produit ? (comment retourner retour)"]
    assert captured["llm"] == ["kifech nraja3 produit ?"]  # le LLM reçoit la question d'origine


@pytest.mark.asyncio
async def test_switch_off_keeps_the_original_search(captured, monkeypatch):
    monkeypatch.setattr(settings, "RAG_ARABIZI_EXPANSION", False)
    await dialogue_manager._handle_message("kifech nraja3 produit ?", "test-arabizi-off", "web")
    assert captured["search"] == ["kifech nraja3 produit ?"]


@pytest.mark.asyncio
async def test_other_languages_are_never_expanded(captured, monkeypatch):
    monkeypatch.setattr(settings, "RAG_ARABIZI_EXPANSION", True)
    await dialogue_manager._handle_message("Je veux payer cash au magasin, c'est possible ?", "test-arabizi-fr", "web")
    assert captured["search"] == ["Je veux payer cash au magasin, c'est possible ?"]


@pytest.mark.integration
def test_search_quality_holds_with_the_expansion(monkeypatch):
    """Garde-fou sur le banc de test : au moins 90 % de bonnes sources dans
    les 4 passages, toutes langues (mesuré : 97 %)."""
    import scripts.evaluate_retrieval as bench
    monkeypatch.setattr(settings, "RAG_RETRIEVAL_MODE", "advanced")
    result = bench.evaluate(bench.load_questions("recherche.json"), "advanced", True)
    hits = sum(s["hits"] for s in result["per_lang"].values())
    total = sum(s["n"] for s in result["per_lang"].values())
    assert hits / total >= 0.90, result["misses"]
