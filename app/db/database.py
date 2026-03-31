"""
Configuration de la connexion PostgreSQL.
On utilise SQLAlchemy ASYNC avec asyncpg.

Pourquoi async ?
- FastAPI est async par nature
- Les requêtes DB ne bloquent pas le serveur
- Peut gérer beaucoup de requêtes en parallèle
"""

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker
)
from sqlalchemy.orm import DeclarativeBase
import logging

from app.config import settings

logger = logging.getLogger(__name__)


# Classe de base pour tous les modèles
# Tous tes modèles vont hériter de cette classe
class Base(DeclarativeBase):
    pass


# Le "moteur" de connexion à la DB
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,   # Affiche le SQL généré si DEBUG=True
    pool_size=5,           # 5 connexions simultanées maximum
    max_overflow=10,       # 10 connexions supplémentaires si besoin
    pool_timeout=30,       # Attendre max 30s pour une connexion
)

# Factory pour créer des sessions
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Les objets restent utilisables après commit
    autocommit=False,
    autoflush=False,
)


async def get_db():
    """
    Dependency Injection FastAPI.

    Usage dans une route :
    async def ma_route(db: AsyncSession = Depends(get_db)):
        ...

    Garantit que la session est toujours fermée après la requête,
    même en cas d'erreur.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables():
    """Crée toutes les tables (dev seulement)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Tables créées avec succès")