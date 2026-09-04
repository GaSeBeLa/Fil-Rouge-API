"""
role_model.py — Table de référence des rôles possibles pour un User
(client / hunter / real_estate_manager).

Choix du groupe (2026-09) : plutôt qu'un CHECK figé sur User.id_role, une
table de lookup pour ajouter/renommer un rôle sans migration de schéma.
"""

from typing import Optional

from sqlmodel import SQLModel, Field


class Role(SQLModel, table=True):
    __tablename__ = "role"

    id: Optional[int] = Field(default=None, primary_key=True)
    libelle: str = Field(max_length=30, unique=True)
