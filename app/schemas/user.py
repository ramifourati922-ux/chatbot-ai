# app/schemas/user.py
"""
Schémas Pydantic pour les utilisateurs.

RÈGLE IMPORTANTE :
- Modèles SQLAlchemy  = structure de la DB
- Schémas Pydantic    = structure de l'API (entrée/sortie)
Ces deux choses sont SÉPARÉES intentionnellement.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
import uuid


class UserCreate(BaseModel):
    """
    Données reçues quand on CRÉE un utilisateur.
    POST /users → ce schéma valide le body de la requête.
    """
    external_id: Optional[str] = Field(
        None,
        max_length=255,
        description="ID externe (numéro WhatsApp, PSID Messenger)"
    )
    channel: str = Field(
        default="web",
        description="Canal : web, whatsapp, ou messenger"
    )
    display_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Nom affiché"
    )
    language: str = Field(
        default="fr",
        max_length=10
    )

    class Config:
        # Exemple affiché dans Swagger UI
        json_schema_extra = {
            "example": {
                "external_id": "21612345678",
                "channel": "whatsapp",
                "display_name": "Ahmed Ben Ali",
                "language": "fr"
            }
        }


class UserUpdate(BaseModel):
    """
    Données reçues quand on MODIFIE un utilisateur.
    PUT /users/{id} → tous les champs sont optionnels.
    """
    display_name: Optional[str] = Field(None, max_length=255)
    language: Optional[str] = Field(None, max_length=10)
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    """
    Données RETOURNÉES à l'utilisateur.
    On ne retourne jamais les mots de passe ou données sensibles.
    """
    id: uuid.UUID
    external_id: Optional[str]
    channel: str
    display_name: Optional[str]
    language: str
    is_active: bool
    created_at: datetime

    class Config:
        # Permet de créer ce schéma depuis un objet SQLAlchemy
        from_attributes = True