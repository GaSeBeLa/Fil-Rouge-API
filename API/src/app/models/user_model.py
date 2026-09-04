"""
user_model.py — Table USER, racine du schéma (Hunter, Client et
RealEstateManager en dépendent tous via id_user).

Choix du groupe (2026-09) : "user" est minimaliste — uniquement
l'essentiel pour créer un compte. first_name/last_name/phone_number/
gender/country_iso ont été redescendus dans Hunter/Client/
RealEstateManager (voir ces fichiers). Le rôle (id_role) est une
nouveauté : une clé étrangère vers la table role (voir role_model.py),
qui n'existait pas du tout dans le schéma précédent.
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
    email: str = Field(max_length=150, unique=True)
    password: str = Field(max_length=80)
    id_role: int = Field(foreign_key="role.id")
