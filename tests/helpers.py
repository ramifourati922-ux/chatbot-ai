# tests/helpers.py
"""
Utilitaires partagés par les tests.

kb_indexed : ChromaDB joignable et base de connaissances indexée. Appelée
au chargement des modules de tests (conditions skipif), donc une seule
fois par exécution (lru_cache) : sans ChromaDB, chaque tentative coûte
environ 5 s, qui se répétaient dans chaque module, même pour
pytest -m "not integration".
"""

from functools import lru_cache

from app.services.rag import vector_store


@lru_cache(maxsize=None)
def kb_indexed() -> bool:
    try:
        return vector_store.count() > 0
    except Exception:
        return False
