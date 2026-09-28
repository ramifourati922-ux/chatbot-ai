# app/db/repositories/conversation_repository.py

from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from sqlalchemy import func, select
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
        processing_time_ms: int = None,
        created_at: Optional[datetime] = None
    ) -> Message:
        """
        Ajouter un message à une conversation.
        role = "user" ou "assistant"
        created_at : horodatage du message. À fournir quand plusieurs
        messages sont écrits dans la même transaction : sinon ils
        reçoivent tous le même now() PostgreSQL (heure de DÉBUT de la
        transaction) et leur ordre par created_at devient arbitraire.
        """
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata_=metadata,
            processing_time_ms=processing_time_ms
        )
        if created_at is not None:
            message.created_at = created_at
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        return message

    async def get_recent_for_user(
        self,
        user_id: uuid.UUID,
        active_since: datetime
    ) -> Optional[Conversation]:
        """
        Dernière conversation de l'utilisateur, si elle a eu de l'activité
        (dernier message, ou démarrage) depuis active_since ; sinon None.
        Sert à rattacher un nouveau message à la conversation en cours.
        """
        last_activity = (
            select(func.coalesce(func.max(Message.created_at), Conversation.started_at))
            .where(Message.conversation_id == Conversation.id)
            .correlate(Conversation)
            .scalar_subquery()
        )
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id, Conversation.status != "closed")
            .where(last_activity >= active_since)
            .order_by(Conversation.started_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

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

    async def get_full_history(self, conversation_id: uuid.UUID) -> List[Message]:
        """Tous les messages de la conversation, dans l'ordre chronologique
        (get_messages, lui, ne renvoie que les derniers)."""
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_with_customer(self, conv_id: uuid.UUID) -> Optional[tuple]:
        """(conversation, identifiant externe du client : n° WhatsApp, PSID
        Messenger, "web:<client_id>"), ou None si introuvable."""
        from app.models.user import User

        result = await self.db.execute(
            select(Conversation, User.external_id)
            .join(User, User.id == Conversation.user_id)
            .where(Conversation.id == conv_id)
        )
        row = result.first()
        return (row[0], row[1]) if row else None

    async def close(self, conv_id: uuid.UUID) -> Optional[Conversation]:
        """Fermer une conversation"""
        from datetime import datetime, timezone
        conv = await self.get_by_id(conv_id)
        if conv:
            conv.status = "closed"
            conv.ended_at = datetime.now(timezone.utc)
            await self.db.flush()
        return conv

    async def list_escalated(self) -> List[dict]:
        """
        Conversations en attente d'un conseiller (statut "escalated") ou
        prises en main par un conseiller (statut "agent"), la plus récente
        escalade en premier. Pour chacune : le client, le canal, le statut,
        la raison et l'heure de la DERNIÈRE escalade (métadonnées du
        message de transfert, voir dialogue_manager._persist_exchange) et
        la question du client : celle qui a déclenché le transfert, ou son
        dernier message si un conseiller a pris la main (il peut avoir
        écrit depuis).
        """
        from app.models.user import User

        rows = await self.db.execute(
            select(Conversation, User)
            .join(User, User.id == Conversation.user_id)
            .where(Conversation.status.in_(("escalated", "agent")))
        )
        escalations = []
        for conv, user in rows.all():
            messages = await self.get_messages(conv.id, limit=50)
            transfer_index = next(
                (i for i in range(len(messages) - 1, -1, -1)
                 if messages[i].role == "assistant" and (messages[i].metadata_ or {}).get("escalated")),
                None,
            )
            if transfer_index is None and conv.status != "agent":
                continue  # statut incohérent (aucun message de transfert) : rien à afficher
            # Prise en main sans transfert (réponse à une conversation jamais
            # escaladée) : pas de raison, datée du début de la conversation.
            transfer = messages[transfer_index] if transfer_index is not None else None
            before = messages if conv.status == "agent" else messages[:transfer_index]
            question = next((m.content for m in reversed(before) if m.role == "user"), "")
            escalations.append({
                "conversation_id": conv.id,
                "customer_id": user.external_id,
                "channel": conv.channel,
                "status": await self.displayed_status(conv),
                "last_question": question,
                "reason": (transfer.metadata_ or {}).get("escalation_reason") if transfer else None,
                "escalated_at": transfer.created_at if transfer else conv.started_at,
            })
        escalations.sort(key=lambda e: e["escalated_at"], reverse=True)
        return escalations

    async def last_agent_message_at(self, conv_id: uuid.UUID) -> Optional[datetime]:
        """Heure du dernier message envoyé par un conseiller, ou None."""
        result = await self.db.execute(
            select(func.max(Message.created_at))
            .where(Message.conversation_id == conv_id, Message.role == "agent")
        )
        return result.scalar_one_or_none()

    async def displayed_status(self, conv: Conversation) -> str:
        """
        Statut à afficher sur /admin. Une prise en main expirée (dernier
        message du conseiller plus vieux qu'AGENT_TAKEOVER_TIMEOUT) s'affiche
        "escalated", comme le bot la traite déjà : sinon une conversation
        abandonnée des deux côtés resterait "Pris en main" indéfiniment, le
        statut en base n'étant réécrit qu'au prochain message du client
        (dialogue_manager.agent_has_the_conversation). Lecture seule.
        """
        if conv.status != "agent":
            return conv.status
        # Import différé : dialogue_manager importe ce module (import
        # circulaire au chargement). Une seule définition du délai.
        from datetime import timezone
        from app.services.dialogue_manager import AGENT_TAKEOVER_TIMEOUT

        last_agent = await self.last_agent_message_at(conv.id)
        if last_agent is None or last_agent < datetime.now(timezone.utc) - AGENT_TAKEOVER_TIMEOUT:
            return "escalated"
        return "agent"

    async def take_over(self, conv: Conversation, agent: str, at: datetime) -> None:
        """
        Un conseiller a répondu : il prend la main, le bot ne répond plus à
        ce client (voir dialogue_manager.agent_has_the_conversation) jusqu'à
        "Marquer traitée" ou 1 h sans message du conseiller.
        """
        conv.status = "agent"
        # Nouveau dict : SQLAlchemy ne détecte pas une modification en place du JSONB
        conv.context = {**(conv.context or {}), "taken_over_by": agent, "taken_over_at": at.isoformat()}
        await self.db.flush()

    async def resolve(self, conv_id: uuid.UUID, resolved_at: datetime) -> Optional[Conversation]:
        """
        Un conseiller a pris en charge l'escalade : statut "resolved" et
        heure de résolution dans le contexte JSON (pas de migration
        nécessaire). Si le client déclenche plus tard une nouvelle
        escalade dans la même conversation, elle repasse à "escalated".
        """
        conv = await self.get_by_id(conv_id)
        if conv:
            conv.status = "resolved"
            # Nouveau dict : SQLAlchemy ne détecte pas une modification en place du JSONB
            conv.context = {**(conv.context or {}), "resolved_at": resolved_at.isoformat()}
            await self.db.flush()
        return conv