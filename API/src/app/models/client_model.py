"""
client_model.py — Spécialisation "client" de User.

Même choix de modélisation que Hunter (voir hunter_model.py) : "id" est
une clé primaire technique indépendante, "id_user" est le lien logique
vers User (UNIQUE côté base).

first_name/last_name/phone_number/gender/country_iso : redescendus
depuis User (choix du groupe, 2026-09).
"""

from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field


class Client(SQLModel, table=True):
    __tablename__ = "client"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))  # Q-SCH-09
    id_user: int = Field(foreign_key="user.id", unique=True)
    first_name: str = Field(max_length=80)
    last_name: str = Field(max_length=80)
    # CHECK cote base : format international d'ADR-007, ex. +33612345678
    # (ck_client_phone_number_format, Q-PRO-08).
    phone_number: str = Field(max_length=20)
    gender: Optional[str] = Field(default=None, max_length=10)
    country_iso: Optional[str] = Field(default=None, max_length=2)
    # Adresse, code postal et ville : tous ou aucun (Q-SCH-01). Les clients
    # repris ont 'non renseigne' et '00000' (Q-SCH-18).
    address: Optional[str] = Field(default=None, max_length=150)
    address_complement: Optional[str] = Field(default=None, max_length=150)
    postal_code: Optional[str] = Field(default=None, max_length=10)
    town: Optional[str] = Field(default=None, max_length=100)
    is_married: Optional[bool] = None
    is_civil_solidarity_pact: Optional[bool] = None
    nb_children: Optional[int] = None
    birth_date: Optional[date] = None
