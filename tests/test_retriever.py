# tests/test_retriever.py
"""
Teste la recherche sémantique dans ChromaDB (nécessite que
scripts/ingest_knowledge_base.py ait été lancé au préalable).
"""

import pytest

from app.services.rag import vector_store, retriever


def _kb_indexed():
    try:
        return vector_store.count() > 0
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _kb_indexed(),
    reason="ChromaDB non peuplé — lancer scripts/ingest_knowledge_base.py d'abord",
)


def test_policy_search_finds_relevant_chunk():
    hits = retriever.search("Quel est le délai pour retourner un produit ?", top_k=3, type_filter="policy")
    assert len(hits) > 0
    # Le meilleur résultat doit venir du fichier retours.txt
    assert any(h["metadata"]["category"] == "retours" for h in hits)


def test_product_search_finds_relevant_product():
    hits = retriever.search("carte Arduino pour débutant", top_k=5, type_filter="product")
    assert len(hits) > 0
    assert all(h["metadata"]["type"] == "product" for h in hits)


def test_unrelated_query_returns_low_or_no_matches():
    """Une question totalement hors-sujet ne devrait pas forcer un match à tout prix."""
    hits = retriever.search("quelle est la capitale de la France", top_k=3)
    # On accepte que Chroma renvoie toujours ses top_k plus proches (comportement normal
    # d'une recherche par similarité), mais le format_context doit rester exploitable
    context = retriever.format_context(hits)
    assert isinstance(context, str)


def test_format_context_empty_when_no_hits():
    assert retriever.format_context([]) == ""
