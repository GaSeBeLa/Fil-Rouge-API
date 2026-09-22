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
    # hire_date : NOT NULL en base. Pour les 6 chasseurs migres, la valeur
    # retenue est la date de creation du compte — hypothese assumee,
    # a confirmer (docker/init-v2/README.md §3.4).
    hire_date: date
    education_level: Optional[str] = Field(default=None, max_length=20)
    # Note : la colonne s'appelle "is_cartet" (tout en minuscules) en base,
    # pas "is_carteT" — PostgreSQL met automatiquement en minuscules les
    # identifiants non "quotés" à la création. On utilise donc le nom réel.
    is_cartet: Optional[bool] = None
    certification_date: Optional[date] = None
    # is_hunter_ai : le chasseur est-il l'agent automatique ?
    is_hunter_ai: Optional[bool] = None
    # Le manager du chasseur (MPD 03 4, 2026-09-22). NOT NULL en base, FK
    # vers real_estate_manager.id_user — donc un id de "user", comme toutes
    # les autres FK du schema. Meme nom tout en minuscules que dans
    # search_request_model.py, ou il designe le manager de la demande.
    id_realestatemanager: int = Field(foreign_key="real_estate_manager.id_user")
