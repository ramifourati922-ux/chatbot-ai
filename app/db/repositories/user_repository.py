# app/db/repositories/user_repository.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from typing import Optional, List
import uuid
import logging

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate

logger = logging.getLogger(__name__)


class UserRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_data: UserCreate) -> User:
        """
        Créer un nouvel utilisateur.
        flush() → envoie à la DB sans committer
        refresh() → recharge l'objet (pour avoir id, timestamps)
        """
        try:
            user = User(**user_data.model_dump(exclude_unset=True))
            self.db.add(user)
            await self.db.flush()
            await self.db.refresh(user)
            logger.info(f"✅ User créé : {user.id}")
            return user
        except IntegrityError:
            await self.db.rollback()
            raise

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """Récupérer un utilisateur par son UUID"""
        result = await self.db.execute(
            select(User).where(
                User.id == user_id,
                User.is_active == True
            )
        )
        return result.scalar_one_or_none()

    async def get_by_external_id(
        self,
        external_id: str,
        channel: str
    ) -> Optional[User]:
        """
        Récupérer un user par son ID externe.
        Utilisé pour WhatsApp (numéro) et Messenger (PSID).
        """
        result = await self.db.execute(
            select(User).where(
                User.external_id == external_id,
                User.channel == channel
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        external_id: str,
        channel: str,
        display_name: str = None
    ) -> tuple[User, bool]:
        """
        Récupère un user existant OU en crée un nouveau.
        Retourne (user, created) :
        - created=True  → vient d'être créé
        - created=False → existait déjà

        Très utile pour WhatsApp/Messenger :
        chaque message peut venir d'un nouveau user.
        """
        user = await self.get_by_external_id(external_id, channel)
        if user:
            return user, False

        user_data = UserCreate(
            external_id=external_id,
            channel=channel,
            display_name=display_name or f"User_{external_id[:8]}"
        )
        user = await self.create(user_data)
        return user, True

    async def update(
        self,
        user_id: uuid.UUID,
        user_data: UserUpdate
    ) -> Optional[User]:
        """Mettre à jour un utilisateur"""
        user = await self.get_by_id(user_id)
        if not user:
            return None

        update_data = user_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def list_all(
        self,
        skip: int = 0,
        limit: int = 20
    ) -> List[User]:
        """Lister les utilisateurs avec pagination"""
        result = await self.db.execute(
            select(User)
            .where(User.is_active == True)
            .offset(skip)
            .limit(limit)
            .order_by(User.created_at.desc())
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        """Compter le total des utilisateurs actifs"""
        from sqlalchemy import func
        result = await self.db.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )
        return result.scalar()