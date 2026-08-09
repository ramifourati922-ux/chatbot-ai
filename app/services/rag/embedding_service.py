# app/services/rag/embedding_service.py
"""
Service d'embeddings — transforme un texte en vecteur numérique pour
la recherche sémantique (RAG).

Modèle : sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
    - 100% local, gratuit, pas d'appel API (tourne sur CPU, pas besoin de GPU)
    - Supporte 50+ langues dont le français, l'anglais et l'ARABE (officiel,
      voir la carte du modèle sur Hugging Face)
    - 384 dimensions → rapide et léger comparé aux modèles 768/1024 dim

Le tunisien (dialecte + arabizi) n'est PAS une langue officiellement
supportée par ce modèle (aucun modèle d'embedding multilingue grand
public ne le supporte nativement — c'est la même limite que pour les
LLM). En pratique :
    - Un message en arabe littéraire ou en français s'embedde bien.
    - Un message en tunisien écrit en lettres ARABES s'embedde
      raisonnablement (le modèle reconnaît l'alphabet/la structure
      arabe même s'il ne "comprend" pas parfaitement le dialecte).
    - Un message en arabizi (latin + chiffres, ex: "3andi mochkla")
      est le cas le plus faible : le modèle le traite comme du texte
      "latin" générique, la qualité de la recherche sémantique en
      pâtit. → C'est pour ça qu'on garde `language_detector.py` en
      amont : si on détecte "tn" en arabizi, on peut choisir de
      traduire/normaliser la requête avant de l'embedder (amélioration
      possible pour une tâche future, pas fait ici).

Alternative multilingue plus forte en arabe : "intfloat/multilingual-e5-large"
(meilleurs benchmarks MTEB pour l'arabe) mais 3x plus lourd (560M
paramètres vs 118M) → plus lent sur CPU. On garde MiniLM par défaut
pour un projet étudiant qui tourne sur laptop ; e5-large reste une
piste d'amélioration si la qualité de recherche s'avère insuffisante.
"""

import logging
from typing import List
from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache()
def _get_model() -> HuggingFaceEmbeddings:
    """
    Charge le modèle une seule fois (le chargement prend quelques
    secondes) et le garde en mémoire pour tous les appels suivants.
    """
    logger.info(f"⏳ Chargement du modèle d'embeddings : {settings.EMBEDDING_MODEL}")
    model = HuggingFaceEmbeddings(
        model_name=f"sentence-transformers/{settings.EMBEDDING_MODEL}",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},  # utile pour la similarité cosinus
    )
    logger.info("✅ Modèle d'embeddings chargé")
    return model


def embed(text: str) -> List[float]:
    """Transforme UN texte en vecteur (liste de floats)."""
    return _get_model().embed_query(text)


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Transforme PLUSIEURS textes en vecteurs (plus efficace qu'appeler embed() en boucle)."""
    return _get_model().embed_documents(texts)
