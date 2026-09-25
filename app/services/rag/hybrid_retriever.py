# app/services/rag/hybrid_retriever.py
"""
Recherche hybride (Advanced RAG) : dense (ChromaDB, existant) + sparse
(BM25Okapi, rank_bm25) fusionnées par Reciprocal Rank Fusion (RRF).

Pourquoi (cf. Module 3 GenAI School, "Advanced RAG" — hybrid search) :
    - Le dense (embeddings MiniLM) capte le SENS mais rate les
      correspondances lexicales exactes : références produit, unités
      techniques ("12V", "5A"), noms de modules ("ESP32", "HC-SR04"),
      mots arabizi que le modèle d'embedding ne connaît pas.
    - BM25 capte exactement ces termes mais ignore les paraphrases.
    - RRF fusionne les deux par RANG, pas par score : les échelles
      (distance cosinus vs score BM25 non borné) sont incomparables,
      le rang ne l'est pas. score(d) = Σ 1 / (k + rang_i(d)), k = 60
      (valeur du papier original, Cormack et al. 2009).

Deux listes classées sont fusionnées :
    1. Dense : la "dual search" du Basic RAG, inchangée (policy et
       product interrogés séparément dans ChromaDB puis fusionnés par
       distance — contournement du manque de recall HNSW, voir
       retriever.search_basic).
    2. Sparse : UN index BM25 sur tout le corpus. BM25 est exact (pas
       d'index approximatif), donc pas besoin de séparer les types, et
       ses scores restent comparables entre politiques et produits.
    ⚠️ Ne PAS faire une liste RRF par type (policy/product) : le 1er
    produit et la 1re politique recevraient le même score RRF quelle
    que soit leur pertinence réelle — testé, ça injectait un produit
    sans rapport (ex: "Circuit intégré 555") dans le top-3 d'une
    question arabe sur la garantie.

L'index BM25 est construit en mémoire au premier appel à partir du
contenu de la collection ChromaDB (même corpus que le dense, aucune
source de vérité en plus, ~3-6 s). On charge aussi les embeddings
stockés, ce qui permet de calculer la distance cosinus EXACTE de tout
candidat remonté uniquement par BM25 (produit scalaire, les vecteurs
sont normalisés). Tous les hits gardent donc un champ `distance`
comparable au Basic RAG → le filtre MAX_RELEVANT_DISTANCE et
get_best_confidence() gardent la même échelle.
Après une ré-ingestion, appeler refresh_index() (ou redémarrer l'API).
"""

import logging
import re
import threading
import unicodedata
from typing import Optional

import numpy as np
from rank_bm25 import BM25Okapi

from app.services.rag import vector_store
from app.services.rag.embedding_service import embed

logger = logging.getLogger(__name__)

RRF_K = 60
# Nombre de candidats par liste (dense, BM25) avant fusion — assez large
# pour alimenter le reranker (top-20).
CANDIDATES_PER_LIST = 20
# Même seuil que le Basic RAG (retriever.MAX_RELEVANT_DISTANCE) : un
# candidat trop éloigné sémantiquement est écarté même si BM25 l'a
# remonté, pour ne pas injecter de bruit lexical dans le prompt.
MAX_RELEVANT_DISTANCE = 0.75
DOC_TYPES = ("policy", "product")
PAGE_SIZE = 500

# Mots-outils fréquents : sans eux, BM25 matche "quel est le délai
# pour..." sur des centaines de chunks sans rapport. Formes sans
# accents/diacritiques (tokenize() les retire avant le filtrage).
_STOPWORDS = {
    # fr
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "l", "et", "ou", "a",
    "au", "aux", "en", "est", "sont", "pour", "par", "sur", "dans", "avec", "que",
    "qui", "quoi", "quel", "quelle", "quels", "quelles", "ce", "cet", "cette", "ces",
    "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "mon", "ma", "mes", "votre",
    "vos", "ne", "pas", "se", "sa", "son", "ses", "y", "comment", "combien",
    # en
    "the", "an", "of", "to", "in", "is", "are", "for", "and", "or", "what",
    "how", "my", "your", "i", "do", "does", "can", "it", "with",
    # ar
    "ما", "ماذا", "هي", "هو", "في", "من", "على", "الى", "عن", "هل", "كم", "و",
    # préfixes "Q:" / "R:" des chunks de politiques
    "q", "r",
}

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list:
    """
    Minuscules + suppression des accents/diacritiques (NFKD) puis
    découpage en mots unicode : marche pour le latin (fr/en/arabizi,
    chiffres conservés : "3andi", "12v") comme pour l'alphabet arabe.
    """
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return [t for t in _TOKEN_RE.findall(text) if t not in _STOPWORDS]


def rrf_fuse(ranked_lists: list, k: int = RRF_K) -> dict:
    """
    Reciprocal Rank Fusion. ranked_lists : listes d'ids, meilleur en
    premier. Retourne {id: score RRF}. Un id absent d'une liste n'y
    contribue simplement pas.
    """
    scores = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return scores


class _CorpusIndex:
    """Corpus complet en mémoire : documents, métadonnées, embeddings, BM25."""

    def __init__(self, ids, documents, metadatas, embeddings):
        self.ids = ids
        self.documents = documents
        self.metadatas = metadatas
        self.types = np.array([m.get("type") for m in metadatas])
        self.pos = {doc_id: i for i, doc_id in enumerate(ids)}
        # embeddings[i] peut valoir None (illisible dans ChromaDB, voir
        # _load_page) : la ligne est alors calculée au premier besoin.
        dim = next((len(e) for e in embeddings if e is not None), 0)
        self.missing = np.array([e is None for e in embeddings], dtype=bool)
        self.embeddings = np.asarray(
            [np.zeros(dim) if e is None else e for e in embeddings], dtype=np.float32
        ).reshape(len(ids), dim)
        self.bm25 = BM25Okapi([tokenize(d) for d in documents])

    def bm25_top(self, query_tokens: list, n: int, type_filter: Optional[str] = None) -> list:
        if not query_tokens or not self.ids:
            return []
        scores = self.bm25.get_scores(query_tokens)
        if type_filter:
            scores = np.where(self.types == type_filter, scores, 0.0)
        top = np.argsort(scores)[::-1][:n]
        # Score 0 = aucun terme de la requête dans le document : pas un match.
        return [self.ids[i] for i in top if scores[i] > 0]

    def distance(self, i: int, query_vec: np.ndarray) -> float:
        """Distance cosinus exacte (vecteurs normalisés → 1 - produit scalaire)."""
        if self.missing[i]:
            self.embeddings[i] = embed(self.documents[i])
            self.missing[i] = False
        return float(1.0 - np.dot(self.embeddings[i], query_vec))


_lock = threading.Lock()
_index: Optional[_CorpusIndex] = None


def _load_page(collection, doc_type: str, offset: int) -> dict:
    """
    ⚠️ Piège ChromaDB (constaté sur chromadb/chroma:latest, 11 109
    chunks) : get(include=["embeddings"]) lève "Error getting embedding"
    sur les derniers enregistrements insérés (~100 produits), alors que
    leurs documents se lisent normalement et qu'ils restent trouvables
    par query(). Dans ce cas on relit la page sans les embeddings ; ils
    seront recalculés localement à la demande (_CorpusIndex.distance),
    même modèle + normalize_embeddings=True qu'à l'ingestion → mêmes
    vecteurs. Pas de recalcul de toute la page d'avance : ~55 ms par
    chunk sur CPU, soit ~30 s pour une page de 500.
    """
    kwargs = {"where": {"type": doc_type}, "limit": PAGE_SIZE, "offset": offset}
    try:
        res = collection.get(include=["documents", "metadatas", "embeddings"], **kwargs)
        return {**res, "embeddings": list(res["embeddings"])}
    except Exception as e:
        res = collection.get(include=["documents", "metadatas"], **kwargs)
        logger.warning(
            f"⚠️ Embeddings illisibles dans ChromaDB ({doc_type}, offset={offset}) : {e} "
            f"→ {len(res['ids'])} embeddings recalculés à la demande"
        )
        return {**res, "embeddings": [None] * len(res["ids"])}


def _build_index() -> _CorpusIndex:
    collection = vector_store.get_collection()
    ids, docs, metas, embs = [], [], [], []
    for doc_type in DOC_TYPES:
        offset = 0
        while True:
            res = _load_page(collection, doc_type, offset)
            if not res["ids"]:
                break
            ids += res["ids"]
            docs += res["documents"]
            metas += res["metadatas"]
            embs += res["embeddings"]
            offset += PAGE_SIZE
    index = _CorpusIndex(ids, docs, metas, embs)
    logger.info(f"✅ Index BM25 construit : {len(ids)} chunks")
    return index


def _get_index() -> _CorpusIndex:
    """Construit l'index une seule fois (premier appel), thread-safe."""
    global _index
    if _index is None:
        with _lock:
            if _index is None:
                _index = _build_index()
    return _index


def refresh_index():
    """À appeler après une ré-ingestion de la knowledge base."""
    global _index
    _index = None


def _dense_ranking(query_embedding, n: int, type_filter: Optional[str]) -> list:
    """Dual search du Basic RAG (un appel par type) fusionnée par distance."""
    pairs = []
    for doc_type in ((type_filter,) if type_filter else DOC_TYPES):
        res = vector_store.query(query_embedding, top_k=n, where={"type": doc_type})
        pairs += zip(res.get("ids", [[]])[0], res.get("distances", [[]])[0])
    return [doc_id for doc_id, _ in sorted(pairs, key=lambda p: p[1])][:n]


def search(
    query_text: str,
    top_k: int = 4,
    type_filter: Optional[str] = None,
    candidates_per_list: int = CANDIDATES_PER_LIST,
) -> list:
    """
    Recherche hybride. Retourne jusqu'à top_k hits triés par score RRF
    décroissant, au même format que retriever.search() :
        {"document", "metadata", "distance", "rrf_score", "dense_rank", "bm25_rank"}
    (dense_rank / bm25_rank = rang dans chaque liste, None si absent —
    utile pour le debug et le rapport).
    """
    index = _get_index()
    query_embedding = embed(query_text)
    q = np.asarray(query_embedding, dtype=np.float32)

    dense_ids = _dense_ranking(query_embedding, candidates_per_list, type_filter)
    bm25_ids = index.bm25_top(tokenize(query_text), candidates_per_list, type_filter)
    dense_ranks = {d: r for r, d in enumerate(dense_ids, start=1)}
    bm25_ranks = {d: r for r, d in enumerate(bm25_ids, start=1)}
    fused = rrf_fuse([dense_ids, bm25_ids])

    hits = []
    for doc_id, score in sorted(fused.items(), key=lambda kv: kv[1], reverse=True):
        i = index.pos.get(doc_id)
        if i is None:  # index BM25 périmé (ré-ingestion sans refresh_index)
            continue
        distance = index.distance(i, q)
        if distance > MAX_RELEVANT_DISTANCE:
            continue
        hits.append({
            "document": index.documents[i],
            "metadata": index.metadatas[i],
            "distance": distance,
            "rrf_score": score,
            "dense_rank": dense_ranks.get(doc_id),
            "bm25_rank": bm25_ranks.get(doc_id),
        })
        if len(hits) >= top_k:
            break
    return hits
