# app/services/semantic_intent.py
"""
Intentions apprises sur des phrases d'exemple (en complément des règles).

Les règles (intent_classifier.py) ne reconnaissent que les tournures
prévues : « vous êtes nuls », « i need your help » ou « nhebek t3awani »
partaient au RAG, qui n'est pas fait pour eux. Ce module compare un
message aux phrases d'exemple de data/intents/exemples.json avec le modèle
d'embeddings déjà chargé pour le RAG (rien de plus à installer ni à
entraîner) et renvoie l'intention de l'exemple le plus proche.

Appelé par dialogue_manager SEULEMENT quand aucune règle n'a tranché, et
seulement si settings.INTENT_MODEL_ENABLED : les règles restent
prioritaires (transfert sûr, explicable, sans modèle).

Décision :
- l'exemple le plus proche (similarité cosinus) donne l'intention ;
- s'il appartient à "general" (contre-exemples : questions normales,
  critiques de produit...), le message reste une question pour le RAG ;
- sinon il faut dépasser un seuil, plus strict pour les transferts
  (INTENT_ESCALATION_THRESHOLD) que pour le reste
  (INTENT_SIMILARITY_THRESHOLD) : un faux transfert occupe un conseiller.
Seuils calibrés sur data/intents/dev.json, qualité mesurée sur
data/intents/test.json (scripts/evaluate_intents.py).
"""

import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

EXAMPLES_PATH = Path(__file__).resolve().parents[2] / "data" / "intents" / "exemples.json"

NEGATIVE = "general"
ESCALATION_INTENTS = frozenset({"human_agent", "frustration"})
LEARNED_INTENTS = ("human_agent", "frustration", "order_tracking", "help")


@dataclass(frozen=True)
class LearnedIntent:
    intent: str
    score: float      # similarité cosinus avec l'exemple le plus proche (0-1)
    example: str      # cet exemple (journaux, débogage)


@dataclass
class _Index:
    labels: list
    texts: list
    matrix: np.ndarray  # une ligne par exemple, vecteurs normalisés


_index: Optional[_Index] = None
_lock = threading.Lock()


def load_examples(path: Path = EXAMPLES_PATH) -> list:
    """[(intention, phrase), ...] : toutes les langues confondues."""
    data = json.loads(path.read_text(encoding="utf-8"))
    pairs = []
    for intent in (*LEARNED_INTENTS, NEGATIVE):
        for phrases in data.get(intent, {}).values():
            pairs.extend((intent, phrase) for phrase in phrases)
    return pairs


def _embed_batch(texts: list) -> list:
    from app.services.rag.embedding_service import embed_batch
    return embed_batch(texts)


def _embed(text: str) -> list:
    from app.services.rag.embedding_service import embed
    return embed(text)


def _normalized(vectors) -> np.ndarray:
    matrix = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    return matrix / np.where(norms == 0, 1, norms)


def _get_index() -> _Index:
    """Vecteurs des exemples, calculés une seule fois (verrou : deux
    requêtes simultanées ne les calculent pas deux fois)."""
    global _index
    if _index is None:
        with _lock:
            if _index is None:
                pairs = load_examples()
                labels = [intent for intent, _ in pairs]
                texts = [phrase for _, phrase in pairs]
                _index = _Index(labels, texts, _normalized(_embed_batch(texts)))
                logger.info(f"🧭 Intentions apprises : {len(texts)} exemples chargés")
    return _index


def reset() -> None:
    """Oublie les vecteurs calculés (tests, ou après modification des exemples)."""
    global _index
    with _lock:
        _index = None


def nearest(text: str) -> LearnedIntent:
    """L'exemple le plus proche du message, quelle que soit son intention
    (y compris "general"), sans seuil."""
    index = _get_index()
    scores = index.matrix @ _normalized(_embed(text))
    best = int(np.argmax(scores))
    return LearnedIntent(index.labels[best], float(scores[best]), index.texts[best])


def threshold_for(intent: str) -> float:
    if intent in ESCALATION_INTENTS:
        return settings.INTENT_ESCALATION_THRESHOLD
    return settings.INTENT_SIMILARITY_THRESHOLD


def classify(text: str) -> Optional[LearnedIntent]:
    """L'intention apprise du message, ou None (question pour le RAG) :
    exemple le plus proche dans "general", ou ressemblance sous le seuil."""
    match = nearest(text)
    if match.intent == NEGATIVE or match.score < threshold_for(match.intent):
        return None
    return match


def warmup() -> None:
    """Calcule les vecteurs des exemples au démarrage (main.lifespan)."""
    _get_index()
