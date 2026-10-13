"""
estate_contact_model.py — Le contact du vendeur d'un bien : 0 ou 1 par bien
(ADR-054). Données personnelles d'un tiers : le client ne les lit jamais
(routes/estate_contact_router.py).

Les formats (téléphone `+33…` d'ADR-007, email, au moins un renseignement)
sont des CHECK de la base : une valeur refusée rend 409.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field


class EstateContact(SQLModel, table=True):
    __tablename__ = "estate_contact"  # pyright: ignore[reportAssignmentType] -- même motif que les autres modèles SQLModel

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # La case « particulier » de l'annonce : obligatoire, vraie ou fausse
    # (ADR-054, questions 1 et 2). Gardée même avec un nom d'agence.
    is_private: bool
    agency_name: Optional[str] = Field(default=None, max_length=100)
    contact_name: Optional[str] = Field(default=None, max_length=100)
    # CHECK côté base : format international d'ADR-007, ex. +33612345678.
    phone_number: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=150)
    id_estate: int = Field(foreign_key="estate.id", unique=True)
    # Rempli par le service avec le compte connecté ; vide : contact importé.
    id_author: Optional[int] = Field(default=None, foreign_key="user.id")
