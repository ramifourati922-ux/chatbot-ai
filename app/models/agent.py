# app/models/agent.py
"""
Modèle Agent — un compte conseiller du tableau de bord /admin.

Chaque conseiller a ses propres identifiants (HTTP Basic), vérifiés
contre cette table : les réponses envoyées, les prises en main et les
résolutions sont rattachées au compte authentifié (traçabilité).

Rôles :
- "conseiller" : conversations transférées (liste, historique, réponse,
  prise en main, "Marquer traitée") ;
- "admin" : idem, plus la gestion des comptes conseillers et /users/.

Le mot de passe n'est jamais stocké : seulement son hachage bcrypt (voir
app/services/agent_auth.py).
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base

ROLES = ("admin", "conseiller")


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="conseiller")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self):
        return f"<Agent {self.username} role={self.role} actif={self.is_active}>"
