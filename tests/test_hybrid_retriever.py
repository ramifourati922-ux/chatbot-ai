# tests/test_hybrid_retriever.py
"""
Teste la recherche hybride BM25 + dense + RRF (Advanced RAG).
Les tests de fusion/tokenisation sont purs ; ceux qui interrogent le
corpus nécessitent ChromaDB peuplé (scripts/ingest_knowledge_base.py).
"""

import pytest

from app.services.rag import retriever, hybrid_retriever
from app.services.rag.hybrid_retriever import rrf_fuse, tokenize
from tests.helpers import kb_indexed as _kb_indexed  # une seule vérification par exécution


needs_kb = pytest.mark.skipif(
    not _kb_indexed(),
    reason="ChromaDB non peuplé — lancer scripts/ingest_knowledge_base.py d'abord",
)


# --- RRF / tokenisation (sans dépendance externe) ---

def test_rrf_rewards_documents_ranked_in_both_lists():
    scores = rrf_fuse([["a", "b", "c"], ["b", "d"]], k=60)
    # "b" est présent dans les 2 listes → devant "a", 1er d'une seule liste
    assert max(scores, key=scores.get) == "b"
    assert scores["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert scores["a"] == pytest.approx(1 / 61)


def test_rrf_empty_lists():
    assert rrf_fuse([[], []]) == {}


def test_tokenize_strips_accents_and_stopwords():
    assert tokenize("Quel est le délai de livraison ?") == ["delai", "livraison"]


def test_tokenize_keeps_arabizi_and_technical_units():
    tokens = tokenize("3andi mochkla m3a alimentation 12V 5A")
    assert "3andi" in tokens and "12v" in tokens and "5a" in tokens


def test_tokenize_arabic_script():
    assert tokenize("ما هي مدة الضمان") == ["مدة", "الضمان"]


# --- Recherche sur le corpus réel ---

@pytest.mark.integration
@needs_kb
def test_hybrid_policy_search_finds_retours():
    hits = hybrid_retriever.search("Quel est le délai pour retourner un produit ?", top_k=3, type_filter="policy")
    assert len(hits) > 0
    assert any(h["metadata"]["category"] == "retours" for h in hits)


@pytest.mark.integration
@needs_kb
def test_hybrid_hits_sorted_by_rrf_and_keep_distance():
    hits = hybrid_retriever.search("carte Arduino Uno R3", top_k=5)
    assert len(hits) > 0
    scores = [h["rrf_score"] for h in hits]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= h["distance"] <= hybrid_retriever.MAX_RELEVANT_DISTANCE for h in hits)


@pytest.mark.integration
@needs_kb
def test_hybrid_mixes_policy_and_products_without_filter():
    """Même garantie que la dual search du Basic RAG : une question SAV
    doit remonter une politique malgré ~11 000 produits."""
    hits = hybrid_retriever.search("Combien de temps dure la garantie ?", top_k=4)
    assert any(h["metadata"]["type"] == "policy" for h in hits)


@pytest.mark.integration
@needs_kb
def test_basic_mode_still_available(monkeypatch):
    monkeypatch.setattr(retriever.settings, "RAG_RETRIEVAL_MODE", "basic")
    hits = retriever.search("carte Arduino pour débutant", top_k=3)
    assert len(hits) > 0
    assert "rrf_score" not in hits[0]


def test_confidence_uses_min_distance_not_first_hit():
    hits = [{"distance": 0.5}, {"distance": 0.3}]
    assert retriever.get_best_confidence(hits) == pytest.approx(0.7)
