# app/services/rag/reranker.py
"""
Reranking cross-encoder (Advanced RAG, étape post-retrieval).

Flux : hybrid_retriever.search() remonte ~20 candidats (rappel large,
bon marché) → le cross-encoder note chaque paire (question, chunk)
ENSEMBLE → on garde les 3 à 5 meilleurs (précision) pour le prompt.

Pourquoi (cf. Module 3 GenAI School, "Advanced RAG" — reranking) : un
bi-encoder (embeddings MiniLM) encode question et document SÉPARÉMENT,
puis compare deux vecteurs ; un cross-encoder lit les deux textes dans
la même passe d'attention et juge leur pertinence mutuelle, bien plus
finement — mais trop lent pour 11 000 chunks, d'où le "retrieve then
rerank" sur un petit nombre de candidats.

Modèle (settings.RERANKER_MODEL) : cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
(118M paramètres), entraîné sur mMARCO = MS MARCO traduit en 14
langues dont le français et l'arabe. MULTILINGUE — indispensable ici
(corpus fr, questions fr/en/ar/tn) : cross-encoder/ms-marco-MiniLM-L-6-v2,
le choix "par défaut" des tutoriels, est anglais uniquement.
Écarté : BAAI/bge-reranker-v2-m3, plus précis mais 568M paramètres →
~1-4 s ajoutées par requête sur CPU sans GPU, incompatible avec une
démo en direct (voir CHANGELOG_ADVANCED_RAG.md, étape 2).
Score = sigmoïde du logit → entre 0 et 1. Forcée explicitement :
l'activation par défaut dépend de la config du modèle (mmarco renvoie
des logits bruts, ~-8 à +10), ce qui rendrait le seuil de confiance
dépendant du modèle choisi.
"""

import logging
from functools import lru_cache

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache()
def _get_model():
    """Chargé une seule fois (plusieurs secondes) — préchargé au démarrage, voir main.py.
    torch et sentence_transformers importés ici (~10 s) : inutiles tant que
    le modèle n'est pas chargé (tests unitaires)."""
    import torch
    from sentence_transformers import CrossEncoder

    logger.info(f"⏳ Chargement du reranker : {settings.RERANKER_MODEL}")
    model = CrossEncoder(
        settings.RERANKER_MODEL,
        max_length=settings.RERANKER_MAX_LENGTH,
        device="cpu",
        activation_fn=torch.nn.Sigmoid(),
    )
    logger.info("✅ Reranker chargé")
    return model


def rerank(query_text: str, hits: list, top_n: int) -> list:
    """
    Trie `hits` par score cross-encoder décroissant et garde les top_n.
    Ajoute à chaque hit : "rerank_score" (0-1) et "hybrid_rank" (rang
    avant reranking, 1 = premier — utile pour le debug et le rapport).
    """
    if not hits:
        return []
    scores = _get_model().predict([(query_text, h["document"]) for h in hits])
    for rank, (hit, score) in enumerate(zip(hits, scores), start=1):
        hit["hybrid_rank"] = rank
        hit["rerank_score"] = float(score)
    return sorted(hits, key=lambda h: h["rerank_score"], reverse=True)[:top_n]


def warmup():
    """Charge le modèle et fait une première prédiction (initialise le graphe torch)."""
    _get_model().predict([("warmup", "warmup")])
