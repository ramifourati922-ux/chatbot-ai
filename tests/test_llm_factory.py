# tests/test_llm_factory.py
"""
Teste que Groq répond correctement dans les 4 langues cibles.

Nécessite une vraie GROQ_API_KEY dans .env (clé gratuite sur
https://console.groq.com/keys). Si absente/placeholder, ces tests
sont automatiquement sautés (skip) plutôt que de faire échouer toute
la suite — normal pour un test qui dépend d'un appel réseau externe
avec une clé secrète.
"""

import pytest

from app.config import settings
from app.services.rag.llm_factory import ask

GROQ_KEY_MISSING = (
    not settings.GROQ_API_KEY or settings.GROQ_API_KEY == "your_groq_api_key_here"
)

pytestmark = pytest.mark.skipif(
    GROQ_KEY_MISSING,
    reason="GROQ_API_KEY non configurée dans .env — voir https://console.groq.com/keys",
)


@pytest.mark.parametrize("language,message", [
    ("fr", "Bonjour, où est ma commande #CMD12345 ?"),
    ("en", "Hello, where is my order?"),
    ("ar", "مرحبا، أين طلبيتي؟"),
    ("tn", "wain commande mte3i, 3andi mochkla"),
])
def test_ask_responds_in_correct_language(language, message):
    response = ask(message, language=language)
    assert isinstance(response, str)
    assert len(response.strip()) > 0
    print(f"\n[{language}] Q: {message}\n[{language}] R: {response}\n")
