# app/services/session_manager.py
"""
Gestion des sessions avec Redis.

TTL = 1 heure.
Fallback en mémoire si Redis n'est pas disponible (utile en dev).
"""

import json
import redis.asyncio as aioredis
from typing import Optional
from datetime import datetime
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Stockage en mémoire (fallback si Redis est down)
_memory_store: dict = {}


class SessionManager:

    SESSION_TTL = 3600
    PREFIX = "session:"

    def __init__(self):
        self._redis_available = True
        try:
            self.redis = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,  # Timeout rapide
            )
        except Exception as e:
            logger.warning(f"⚠️ Redis non disponible, fallback mémoire: {e}")
            self._redis_available = False
            self.redis = None

    async def _redis_get(self, key: str) -> Optional[str]:
        """Lire depuis Redis avec fallback mémoire"""
        if not self._redis_available:
            return _memory_store.get(key)
        try:
            return await self.redis.get(key)
        except Exception as e:
            logger.warning(f"⚠️ Redis get failed, fallback mémoire: {e}")
            self._redis_available = False
            return _memory_store.get(key)

    async def _redis_set(self, key: str, value: str, ttl: int):
        """Écrire dans Redis avec fallback mémoire"""
        if not self._redis_available:
            _memory_store[key] = value
            return
        try:
            await self.redis.setex(key, ttl, value)
        except Exception as e:
            logger.warning(f"⚠️ Redis set failed, fallback mémoire: {e}")
            self._redis_available = False
            _memory_store[key] = value

    async def _redis_expire(self, key: str, ttl: int):
        if not self._redis_available:
            return
        try:
            await self.redis.expire(key, ttl)
        except Exception:
            pass

    async def _redis_delete(self, key: str):
        if not self._redis_available:
            _memory_store.pop(key, None)
            return
        try:
            await self.redis.delete(key)
        except Exception:
            _memory_store.pop(key, None)

    async def get_session(self, session_id: str) -> Optional[dict]:
        """Récupérer une session existante."""
        key = f"{self.PREFIX}{session_id}"
        data = await self._redis_get(key)
        if data:
            await self._redis_expire(key, self.SESSION_TTL)
            return json.loads(data)
        return None

    async def create_session(
        self,
        session_id: str,
        channel: str = "web",
        user_id: str = None
    ) -> dict:
        """Créer une nouvelle session"""
        session = {
            "session_id": session_id,
            "channel": channel,
            "user_id": user_id,
            "messages": [],
            # rag_attempts_count : nombre de messages consécutifs passés par
            # le RAG sans escalade ni signal de satisfaction — sert à
            # détecter une boucle (le bot n'arrive pas à aider) et forcer
            # une escalade automatique (voir dialogue_manager.handle_message).
            "context": {"rag_attempts_count": 0},
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat()
        }
        await self._save(session_id, session)
        logger.info(f"✅ Session créée : {session_id}")
        return session

    async def get_or_create(self, session_id: str, channel: str = "web") -> dict:
        session = await self.get_session(session_id)
        if session:
            return session
        return await self.create_session(session_id, channel)

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict = {}
    ):
        """Ajouter un message à la session (max 20 messages)."""
        session = await self.get_session(session_id)
        if not session:
            return

        session["messages"].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata
        })

        if len(session["messages"]) > 20:
            session["messages"] = session["messages"][-20:]

        session["last_activity"] = datetime.now().isoformat()
        await self._save(session_id, session)

    async def update_context(self, session_id: str, updates: dict):
        """Mettre à jour le contexte de la session."""
        session = await self.get_session(session_id)
        if session:
            session["context"].update(updates)
            await self._save(session_id, session)

    async def get_context(self, session_id: str) -> dict:
        session = await self.get_session(session_id)
        return session.get("context", {}) if session else {}

    async def increment_rag_attempts(self, session_id: str) -> int:
        """Incrémente rag_attempts_count et retourne la nouvelle valeur.
        Appelé à chaque message qui part vers le RAG (ni escalade, ni
        signal de satisfaction) — sert à détecter une boucle où le bot
        n'arrive pas à aider plusieurs fois de suite."""
        session = await self.get_session(session_id)
        if not session:
            return 0
        count = session["context"].get("rag_attempts_count", 0) + 1
        session["context"]["rag_attempts_count"] = count
        await self._save(session_id, session)
        return count

    async def reset_rag_attempts(self, session_id: str):
        """Remet rag_attempts_count à 0. Appelé à chaque escalade (peu
        importe la raison) et sur un signal de satisfaction client — le
        compteur doit refléter des échecs consécutifs, pas un total
        cumulé sur toute la session."""
        session = await self.get_session(session_id)
        if not session:
            return
        session["context"]["rag_attempts_count"] = 0
        await self._save(session_id, session)

    async def get_history(self, session_id: str) -> list:
        session = await self.get_session(session_id)
        return session.get("messages", []) if session else []

    async def clear_context_key(self, session_id: str, key: str):
        session = await self.get_session(session_id)
        if session and key in session["context"]:
            del session["context"][key]
            await self._save(session_id, session)

    async def delete_session(self, session_id: str):
        await self._redis_delete(f"{self.PREFIX}{session_id}")
        logger.info(f"🗑️ Session supprimée : {session_id}")

    async def _save(self, session_id: str, session: dict):
        key = f"{self.PREFIX}{session_id}"
        await self._redis_set(
            key,
            json.dumps(session, ensure_ascii=False),
            self.SESSION_TTL
        )
