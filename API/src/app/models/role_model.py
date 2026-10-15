"""
role_model.py — Table de référence des rôles qui ont une fiche :
Client, Hunter, Manager (chantier PRF, PRF8).

Chaque fiche la cite par role_wording ; Admin et Reader, sans fiche,
vivent dans User.system_role.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field


class Role(SQLModel, table=True):
    __tablename__ = "role"  # pyright: ignore[reportAssignmentType] -- même motif que les autres modèles SQLModel

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))  # Q-SCH-09
    # wording : CHECK cote base — 'Admin', 'Client', 'Hunter', 'Manager',
    # 'Reader' (lecture seule, Q14, LOT12).
    # La colonne s'appelait "libelle" dans l'ancien schema (12 tables).
    wording: str = Field(max_length=20, unique=True)
