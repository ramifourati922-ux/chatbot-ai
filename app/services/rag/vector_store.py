# app/services/rag/vector_store.py
"""
Client ChromaDB — stocke et interroge les embeddings de la knowledge base.

ChromaDB tourne dans Docker (docker-compose.yml, port 8001 côté hôte
→ port 8000 côté conteneur). On s'y connecte en HTTP, pas en local
embarqué, pour que plusieurs process (API + scripts d'ingestion)
partagent la même base sans conflit de fichiers.
"""

import logging
from functools import lru_cache
from typing import Optional

import chromadb

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache()
def get_client() -> chromadb.HttpClient:
    return chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)


@lru_cache()
def get_collection():
    """
    Une seule collection pour toute la knowledge base (politiques +
    produits), différenciée par le champ de métadonnée `type`
    ("policy" ou "product") — plus simple à interroger avec un seul
    filtre optionnel plutôt que de gérer deux collections séparées.
    """
    client = get_client()
    return client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},  # cohérent avec normalize_embeddings=True côté embedding_service
    )


def upsert(ids: list, embeddings: list, documents: list, metadatas: list, batch_size: int = 500):
    """Insère/met à jour des documents par lots (évite les requêtes HTTP trop grosses)."""
    collection = get_collection()
    total = len(ids)
    for i in range(0, total, batch_size):
        collection.upsert(
            ids=ids[i:i + batch_size],
            embeddings=embeddings[i:i + batch_size],
            documents=documents[i:i + batch_size],
            metadatas=metadatas[i:i + batch_size],
        )
    logger.info(f"✅ {total} documents indexés dans la collection '{settings.CHROMA_COLLECTION_NAME}'")


def query(query_embedding: list, top_k: int = 5, where: Optional[dict] = None):
    """
    Recherche les documents les plus proches sémantiquement d'un vecteur de requête.

    ⚠️ Piège ChromaDB : passer `where=None` explicitement (au lieu de ne
    pas passer l'argument du tout) fait renvoyer 0 résultat au lieu de
    "pas de filtre" — d'où le kwargs conditionnel ci-dessous.
    """
    collection = get_collection()
    kwargs = {"query_embeddings": [query_embedding], "n_results": top_k}
    if where:
        kwargs["where"] = where
    return collection.query(**kwargs)


def count() -> int:
    return get_collection().count()


def reset_collection():
    """Supprime et recrée la collection (utile pour ré-indexer proprement depuis zéro)."""
    client = get_client()
    try:
        client.delete_collection(settings.CHROMA_COLLECTION_NAME)
    except Exception:
        pass
    get_collection.cache_clear()
    return get_collection()
