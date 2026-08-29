# app/services/rag/retriever.py
"""
Recherche sémantique dans la knowledge base indexée (ChromaDB).

Flux : texte utilisateur → embedding → recherche des chunks les plus
proches → formatage en contexte texte à injecter dans le prompt LLM
(voir llm_factory.ask(..., extra_context=...)).
"""

import logging
from typing import Optional

from app.services.rag.embedding_service import embed
from app.services.rag import vector_store

logger = logging.getLogger(__name__)

# Distance cosinus max acceptée pour qu'un résultat soit considéré
# pertinent (0 = identique, 2 = opposé). Au-delà, on préfère ne rien
# donner au LLM plutôt que du bruit non pertinent — c'est ce qui évite
# les réponses hors-sujet "collées" à un chunk qui n'a rien à voir.
MAX_RELEVANT_DISTANCE = 0.75


def _query_one(query_embedding, top_k, type_filter: Optional[str]) -> list:
    where = {"type": type_filter} if type_filter else None
    results = vector_store.query(query_embedding, top_k=top_k, where=where)
    hits = []
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    for doc, meta, dist in zip(documents, metadatas, distances):
        if dist <= MAX_RELEVANT_DISTANCE:
            hits.append({"document": doc, "metadata": meta, "distance": dist})
    return hits


def search(query_text: str, top_k: int = 4, type_filter: Optional[str] = None) -> list:
    """
    Retourne les chunks les plus pertinents pour `query_text`.
    type_filter : "policy" ou "product" pour restreindre la recherche.

    ⚠️ Quand type_filter=None, on interroge séparément policy et product
    PUIS on fusionne — plutôt qu'une seule requête non filtrée sur toute
    la collection. Raison : la collection est très déséquilibrée
    (~11 000 produits vs ~60 chunks de politiques), et l'index approximatif
    HNSW de ChromaDB perd en précision (recall) sur une recherche globale
    dans ce cas — il peut rester "coincé" dans le cluster dense des
    produits et rater un chunk de politique bien plus pertinent (distance
    beaucoup plus faible) qui existe pourtant. Interroger chaque sous-
    ensemble séparément (bien plus homogène) puis fusionner par distance
    est plus lent (2 requêtes) mais fiable.
    """
    query_embedding = embed(query_text)

    if type_filter:
        return sorted(_query_one(query_embedding, top_k, type_filter), key=lambda h: h["distance"])[:top_k]

    policy_hits = _query_one(query_embedding, top_k, "policy")
    product_hits = _query_one(query_embedding, top_k, "product")
    merged = sorted(policy_hits + product_hits, key=lambda h: h["distance"])
    return merged[:top_k]


def get_best_confidence(hits: list) -> float:
    """
    Score de confiance RAG basé sur la distance cosinus du meilleur hit
    (1 - distance) — utilisé par dialogue_manager pour décider d'une
    escalade automatique quand le contexte trouvé est peu fiable (voir
    RAG_CONFIDENCE_THRESHOLD). 0.0 si hits est vide (aucun document
    trouvé du tout = confiance nulle).

    hits est déjà trié par distance croissante (voir search()), donc
    hits[0] est toujours le meilleur match.
    """
    if not hits:
        return 0.0
    return 1 - hits[0]["distance"]


def format_context(hits: list) -> str:
    """Formate les résultats de recherche en texte à injecter dans le prompt LLM."""
    if not hits:
        return ""
    lines = []
    for hit in hits:
        lines.append(f"- {hit['document']}")
    return "\n".join(lines)


def search_and_format(query_text: str, top_k: int = 4, type_filter: Optional[str] = None) -> str:
    """Raccourci : recherche + formatage en une seule fonction."""
    hits = search(query_text, top_k=top_k, type_filter=type_filter)
    if not hits:
        logger.info(f"🔍 Aucun résultat pertinent trouvé pour : {query_text[:60]!r}")
    return format_context(hits)
