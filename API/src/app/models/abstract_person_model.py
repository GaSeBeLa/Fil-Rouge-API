"""
abstract_person_model.py — Les champs communs aux trois fiches de profil.

Client, Hunter et RealEstateManager portent les mêmes sept champs :
created_at, id_user, first_name, last_name, phone_number, gender,
country_iso. Ils sont écrits une seule fois ici, et les trois classes en
héritent (chantier PRF, décision de Seb du 2026-10-15).

AbstractPerson n'a PAS `table=True` : ce n'est pas une table. Chaque
fiche reste une table à part dans docker/init-v3/01, avec sa propre clé
primaire "id" (déclarée dans la classe fille, pas ici).

Une classe fille peut redéclarer un champ pour le changer :
- Client redéclare country_iso obligatoire (ADR-053, P3) ;
- chaque fiche redéclare id_user pour garder sa description Swagger.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field


class AbstractPerson(SQLModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))  # Q-SCH-09
    id_user: int = Field(foreign_key="user.id", unique=True)
    first_name: str = Field(max_length=80)
    last_name: str = Field(max_length=80)
    # CHECK cote base : format international d'ADR-007, ex. +33612345678
    # (ck_<table>_phone_number_format, Q-PRO-08).
    phone_number: str = Field(max_length=20)
    gender: Optional[str] = Field(default=None, max_length=10)
    country_iso: Optional[str] = Field(default=None, max_length=2)
