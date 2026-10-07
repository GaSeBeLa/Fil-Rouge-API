"""
role_model.py — Table de référence des rôles possibles pour un User
(Admin / Client / Hunter / Manager / Reader).

Choix du groupe (2026-09) : plutôt qu'un CHECK figé sur User.id_role, une
table de lookup pour ajouter/renommer un rôle sans migration de schéma.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field


class Role(SQLModel, table=True):
    __tablename__ = "role"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))  # Q-SCH-09
    # wording : CHECK cote base — 'Admin', 'Client', 'Hunter', 'Manager',
    # 'Reader' (lecture seule, Q14, LOT12).
    # La colonne s'appelait "libelle" dans l'ancien schema (12 tables).
    wording: str = Field(max_length=20, unique=True)
