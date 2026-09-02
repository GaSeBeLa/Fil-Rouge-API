"""
user_model.py — Table USER, racine du schéma (Hunter, Client et
RealEstateManager en dépendent tous via id_user).
"""

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    __tablename__ = "user"  # "user" est un mot réservé SQL ; SQLAlchemy le
    # met automatiquement entre guillemets doubles à la génération des
    # requêtes, comme le fait le script SQL — pas d'action supplémentaire
    # nécessaire de notre côté.

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    first_name: str = Field(max_length=80)
    last_name: str = Field(max_length=80)
    email: str = Field(max_length=150, unique=True)
    password: str = Field(max_length=80)
    phone_number: str = Field(max_length=20)
    gender: Optional[str] = Field(default=None, max_length=10)
    country_iso: Optional[str] = Field(default=None, max_length=2)
