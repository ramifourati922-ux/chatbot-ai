# app/models/conversation.py

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Clé étrangère → lié à la table users
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    channel: Mapped[str] = mapped_column(String(20), nullable=False)

    # Statut de la conversation
    # "active" → en cours
    # "closed" → terminée
    # "escalated" → transférée à un humain
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False
    )

    # Sujet détecté : "sav", "ecommerce", "general"
    topic: Mapped[str] = mapped_column(
        String(50),
        nullable=True
    )

    # Contexte JSON : état de la conversation
    # Ex: {"awaiting": "order_number", "last_intent": "check_order"}
    context: Mapped[dict] = mapped_column(
        JSONB,
        default={},
        nullable=True
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    ended_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relation : une conversation a plusieurs messages
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Conversation id={self.id} status={self.status}>"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # "user" = message de l'humain
    # "assistant" = réponse du chatbot
    # "system" = message système
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Métadonnées : intent détecté, score, source RAG...
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        default={},
        nullable=True
    )

    # Temps de traitement en millisecondes (pour les stats)
    processing_time_ms: Mapped[int] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<Message role={self.role} content={self.content[:50]}>"