"""
Toutes les variables d'environnement centralisées ici.
Pydantic Settings valide automatiquement les types.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Chatbot IA"
    DEBUG: bool = False
    SECRET_KEY: str = "change-this-secret"

    # Base de données
    DATABASE_URL: str
    POSTGRES_DB: str = "chatbot_db"
    POSTGRES_USER: str = "chatbot_user"
    POSTGRES_PASSWORD: str = "secret123"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Groq (Phase 3 — LLM gratuit, PAS d'OpenAI)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_FALLBACK_MODEL: str = "openai/gpt-oss-20b"

    # ChromaDB (Phase 3 — Vector DB pour le RAG)
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001
    CHROMA_COLLECTION_NAME: str = "liss_strike_kb"

    # Embeddings (Phase 3 — local, gratuit, multilingue FR/EN/AR)
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # WhatsApp (Phase 5)
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None
    WHATSAPP_ACCESS_TOKEN: Optional[str] = None
    WHATSAPP_VERIFY_TOKEN: Optional[str] = None

    # Messenger (Phase 5)
    MESSENGER_PAGE_ACCESS_TOKEN: Optional[str] = None
    MESSENGER_VERIFY_TOKEN: Optional[str] = None

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()