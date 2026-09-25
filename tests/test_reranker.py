# tests/test_reranker.py
"""
Teste le reranking cross-encoder (Advanced RAG).
La logique de tri est testée avec un faux modèle ; les tests sur le
vrai modèle (BAAI/bge-reranker-v2-m3, ~2,3 Go) ne tournent que s'il est
déjà dans le cache Hugging Face local, et ceux sur le corpus que si
ChromaDB est peuplé.
"""

import pytest
from huggingface_hub import try_to_load_from_cache

from app.config import settings
from app.services.rag import vector_store, retriever, reranker


class _FakeModel:
    """Score = nombre de mots de la question présents dans le document."""

    def predict(self, pairs):
        return [sum(w in doc.lower() for w in q.lower().split()) / 10 for q, doc in pairs]


@pytest.fixture
def fake_model(monkeypatch):
    monkeypatch.setattr(reranker, "_get_model", lambda: _FakeModel())


def _model_cached():
    return isinstance(try_to_load_from_cache(settings.RERANKER_MODEL, "model.safetensors"), str)


def _kb_indexed():
    try:
        return vector_store.count() > 0
    except Exception:
        return False


needs_model = pytest.mark.skipif(not _model_cached(), reason=f"{settings.RERANKER_MODEL} pas en cache local")
needs_kb = pytest.mark.skipif(not _kb_indexed(), reason="ChromaDB non peuplé")


def test_rerank_orders_by_score_and_truncates(fake_model):
    hits = [{"document": "garantie"}, {"document": "livraison express rapide"}, {"document": "livraison"}]
    out = reranker.rerank("livraison express", hits, top_n=2)
    assert [h["document"] for h in out] == ["livraison express rapide", "livraison"]
    assert out[0]["hybrid_rank"] == 2 and out[1]["hybrid_rank"] == 3
    assert out[0]["rerank_score"] >= out[1]["rerank_score"]


def test_rerank_empty(fake_model):
    assert reranker.rerank("x", [], top_n=3) == []


@needs_kb
def test_advanced_mode_reranks_hybrid_candidates(fake_model, monkeypatch):
    monkeypatch.setattr(retriever.settings, "RAG_RETRIEVAL_MODE", "advanced")
    hits = retriever.search("délai de retour produit", top_k=4)
    assert 0 < len(hits) <= 4
    assert all("rerank_score" in h and "rrf_score" in h for h in hits)


@needs_model
def test_real_reranker_prefers_relevant_multilingual():
    hits = [
        {"document": "Q: Quels sont les moyens de paiement acceptés ? R: Carte bancaire, espèces à la livraison."},
        {"document": "Q: Quelle est la durée de garantie ? R: Tous nos produits sont garantis 6 mois."},
    ]
    # Question en arabe, documents en français : le reranker doit être multilingue
    out = reranker.rerank("ما هي مدة الضمان", hits, top_n=2)
    assert "garantie" in out[0]["document"]
    assert 0.0 <= out[1]["rerank_score"] <= out[0]["rerank_score"] <= 1.0


