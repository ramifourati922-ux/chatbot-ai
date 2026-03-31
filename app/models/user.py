# app/models/user.py
"""
Modèle User — représente un utilisateur du chatbot.
Un utilisateur peut venir de Web, WhatsApp ou Messenger.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    # UUID = identifiant unique universel
    # Plus sécurisé que Integer (on ne peut pas deviner les IDs)
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # ID externe : numéro WhatsApp, PSID Messenger, etc.
    external_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True        # Index = recherche plus rapide
    )

    # D'où vient l'utilisateur ?
    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="web"
        # Valeurs : "web", "whatsapp", "messenger"
    )

    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=True
    )

    language: Mapped[str] = mapped_column(
        String(10),
        default="fr",
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    # JSONB = JSON stocké efficacement dans PostgreSQL
    # Utile pour stocker des infos flexibles
    extra_data: Mapped[dict] = mapped_column(
        JSONB,
        default={},
        nullable=True
    )

    # Timestamps automatiques
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    def __repr__(self):
        return f"<User id={self.id} channel={self.channel} name={self.display_name}>"