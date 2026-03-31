# app/models/__init__.py
# Importer tous les modèles ici
# Alembic en a besoin pour générer les migrations

from app.models.user import User
from app.models.conversation import Conversation, Message