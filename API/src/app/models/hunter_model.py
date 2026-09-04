"""
hunter_model.py — Spécialisation "chasseur immobilier" de User.

Rappel du choix de modélisation du groupe : "id" est une clé primaire
technique indépendante, "id_user" est le lien logique vers User (UNIQUE
côté base). Objectif : découpler la clé technique de cette table de la
façon dont "user.id" est généré (portabilité en cas de changement de
SGBD). Toutes les FK du reste du schéma pointent vers id_user, pas vers
id — même choix pour Client et RealEstateManager (voir client_model.py,
real_estate_manager_model.py).

first_name/last_name/phone_number/gender/country_iso : redescendus
depuis User (choix du groupe, 2026-09).
"""

from datetime import date
from typing import Optional

from sqlmodel import SQLModel, Field


class Hunter(SQLModel, table=True):
    __tablename__ = "hunter"

    id: Optional[int] = Field(default=None, primary_key=True)
    id_user: int = Field(foreign_key="user.id", unique=True)
    first_name: str = Field(max_length=80)
    last_name: str = Field(max_length=80)
    phone_number: str = Field(max_length=20)
    gender: Optional[str] = Field(default=None, max_length=10)
    country_iso: Optional[str] = Field(default=None, max_length=2)
    company_name: Optional[str] = Field(default=None, max_length=80)
    education_level: Optional[str] = Field(default=None, max_length=20)
    # Note : la colonne s'appelle "is_cartet" (tout en minuscules) en base,
    # pas "is_carteT" — PostgreSQL met automatiquement en minuscules les
    # identifiants non "quotés" à la création. On utilise donc le nom réel.
    is_cartet: Optional[bool] = None
    certification_date: Optional[date] = None
    commission_rate: Optional[float] = None
