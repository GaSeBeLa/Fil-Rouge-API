"""
client_model.py — Spécialisation "client" de User.

Même choix de modélisation que Hunter (voir hunter_model.py) : "id" est
une clé primaire technique indépendante, "id_user" est le lien logique
vers User (UNIQUE côté base).
"""

from datetime import date
from typing import Optional

from sqlmodel import SQLModel, Field


class Client(SQLModel, table=True):
    __tablename__ = "client"

    id: Optional[int] = Field(default=None, primary_key=True)
    id_user: int = Field(foreign_key="user.id", unique=True)
    address: Optional[str] = Field(default=None, max_length=150)
    address_complement: Optional[str] = Field(default=None, max_length=150)
    postal_code: Optional[str] = Field(default=None, max_length=10)
    town: Optional[str] = Field(default=None, max_length=100)
    is_married: Optional[bool] = None
    is_civil_solidarity_pact: Optional[bool] = None
    nb_children: Optional[int] = None
    birth_date: Optional[date] = None
