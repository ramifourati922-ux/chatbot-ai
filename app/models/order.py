# app/models/order.py
"""
Modèle Order — une commande client, consultée par le suivi de commande
(app/services/order_tracking.py) sans passer par le LLM : statut et dates
viennent de la base, jamais d'une génération.

Données de démonstration uniquement (scripts/seed_demo_orders.py) : pas
d'intégration avec une vraie boutique en ligne.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base

ORDER_STATUSES = ("recue", "en_preparation", "expediee", "livree", "annulee")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('recue', 'en_preparation', 'expediee', 'livree', 'annulee')",
            name="ck_orders_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Format CMD-AAAA-NNNNN, ex. CMD-2026-00123 (voir intent_classifier.ORDER_NUMBER_PATTERN)
    order_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    # Client non identifié possible ; la suppression d'un client conserve ses commandes
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="recue")
    # [{"name": "Arduino Uno R3", "quantity": 2}, ...]
    items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    estimated_delivery: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    def __repr__(self):
        return f"<Order {self.order_number} status={self.status}>"
