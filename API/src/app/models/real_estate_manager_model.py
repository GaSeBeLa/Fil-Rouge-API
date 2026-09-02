"""
real_estate_manager_model.py — Spécialisation "gestionnaire immobilier"
de User.

Même choix de modélisation que Hunter (voir hunter_model.py) : "id" est
une clé primaire technique indépendante, "id_user" est le lien logique
vers User (UNIQUE côté base).
"""

from typing import Optional

from sqlmodel import SQLModel, Field


class RealEstateManager(SQLModel, table=True):
    __tablename__ = "real_estate_manager"

    id: Optional[int] = Field(default=None, primary_key=True)
    id_user: int = Field(foreign_key="user.id", unique=True)
    company_name: Optional[str] = Field(default=None, max_length=80)
