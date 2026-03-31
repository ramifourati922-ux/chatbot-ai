# app/db/repositories/conversation_repository.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
import uuid
import logging

from app.models.conversation import Conversation, Message
from app.db.database import Base

logger = logging.getLogger(__name__)


class ConversationRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: uuid.UUID,
        channel: str,
        topic: str = "general"
    ) -> Conversation:
        """Créer une nouvelle conversation"""
        conv = Conversation(
            user_id=user_id,
            channel=channel,
            topic=topic,
            status="active"
        )
        self.db.add(conv)
        await self.db.flush()
        await self.db.refresh(conv)
        logger.info(f"✅ Conversation créée : {conv.id}")
        return conv

    async def get_by_id(
        self,
        conv_id: uuid.UUID
    ) -> Optional[Conversation]:
        """Récupérer une conversation par ID"""
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )
        return result.scalar_one_or_none()

    async def add_message(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        metadata: dict = {},
        processing_time_ms: int = None
    ) -> Message:
        """
        Ajouter un message à une conversation.
        role = "user" ou "assistant"
        """
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata_=metadata,
            processing_time_ms=processing_time_ms
        )
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        return message

    async def get_messages(
        self,
        conversation_id: uuid.UUID,
        limit: int = 20
    ) -> List[Message]:
        """Récupérer les derniers messages d'une conversation"""
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = list(result.scalars().all())
        return list(reversed(messages))  # Ordre chronologique

    async def close(self, conv_id: uuid.UUID) -> Optional[Conversation]:
        """Fermer une conversation"""
        from datetime import datetime, timezone
        conv = await self.get_by_id(conv_id)
        if conv:
            conv.status = "closed"
            conv.ended_at = datetime.now(timezone.utc)
            await self.db.flush()
        return conv