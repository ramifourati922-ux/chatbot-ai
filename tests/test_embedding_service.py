# tests/test_embedding_service.py
"""
Vérifie que le modèle d'embeddings multilingue :
1. produit des vecteurs de la bonne dimension
2. rapproche sémantiquement des phrases similaires même dans des
   langues différentes (FR/EN/AR) — c'est le vrai test de "comprend
   bien le multilingue", pas juste "ne plante pas".
"""

import numpy as np
import pytest

from app.services.rag.embedding_service import embed, embed_batch


def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def test_embed_returns_vector():
    vec = embed("Bonjour, où est ma commande ?")
    assert isinstance(vec, list)
    assert len(vec) == 384  # dimension du modèle MiniLM
    assert all(isinstance(x, float) for x in vec)


def test_embed_batch():
    vecs = embed_batch(["Bonjour", "Hello", "مرحبا"])
    assert len(vecs) == 3
    assert all(len(v) == 384 for v in vecs)


def test_cross_lingual_similarity():
    """
    Une même question posée en FR/EN/AR doit être PLUS proche
    sémantiquement entre elle qu'avec une question sans rapport.
    C'est ça qui rend le RAG multilingue possible : la recherche
    dans ChromaDB fonctionnera même si le client écrit dans une
    langue différente de la base de connaissances.
    """
    fr = embed("Où est ma commande ?")
    en = embed("Where is my order?")
    ar = embed("أين طلبيتي؟")
    unrelated = embed("Quel temps fait-il aujourd'hui ?")

    sim_fr_en = cosine_similarity(fr, en)
    sim_fr_ar = cosine_similarity(fr, ar)
    sim_fr_unrelated = cosine_similarity(fr, unrelated)

    print(f"\nfr<->en: {sim_fr_en:.3f} | fr<->ar: {sim_fr_ar:.3f} | fr<->unrelated: {sim_fr_unrelated:.3f}")

    assert sim_fr_en > sim_fr_unrelated
    assert sim_fr_ar > sim_fr_unrelated
