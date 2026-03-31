# app/api/routes/users.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.db.database import get_db
from app.db.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate, UserResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un utilisateur"
)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Créer un nouvel utilisateur du chatbot"""
    repo = UserRepository(db)
    user = await repo.create(user_data)
    return user


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Récupérer un utilisateur"
)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Récupérer un utilisateur par son ID"""
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Utilisateur non trouvé"
        )
    return user


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Modifier un utilisateur"
)
async def update_user(
    user_id: uuid.UUID,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Modifier un utilisateur existant"""
    repo = UserRepository(db)
    user = await repo.update(user_id, user_data)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Utilisateur non trouvé"
        )
    return user


@router.get(
    "/",
    response_model=list[UserResponse],
    summary="Lister les utilisateurs"
)
async def list_users(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Lister tous les utilisateurs (avec pagination)"""
    repo = UserRepository(db)
    return await repo.list_all(skip=skip, limit=limit)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Désactiver un utilisateur"
)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Désactiver un utilisateur (soft delete)"""
    repo = UserRepository(db)
    user = await repo.update(user_id, UserUpdate(is_active=False))
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")