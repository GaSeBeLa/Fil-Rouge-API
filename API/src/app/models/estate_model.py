"""
estate_model.py — Les biens immobiliers (annonces) proposés aux clients.

Deux choses à savoir avant d'écrire du code sur cette table :

- **`price` est en euros**, `NUMERIC(12,2)`, donc `Decimal` ici — jamais
  `float` : un flottant ne représente pas exactement un centime, et la
  règle de rémunération exige l'arrondi au centime. Voir
  `docker/init-v2/README.md` §1.
- **L'énergie est décrite en cinq colonnes** (`energy_class`,
  `energy_class_scheme`, `energy_class_date`, `energy_kwh_m2`,
  `energy_co2_m2`), et non plus par l'ancien `energetic_score`, qui
  n'existe plus.

Les colonnes à liste fermée (`estate_type`, `typology`, `floor`,
`energy_class`, `country_iso`) portent un CHECK côté base : c'est
PostgreSQL qui rejette une valeur hors liste, pas SQLModel.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlmodel import SQLModel, Field


class Estate(SQLModel, table=True):
    __tablename__ = "estate"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reference: str = Field(max_length=50, unique=True)
    country_iso: Optional[str] = Field(default=None, max_length=2)
    estate_type: str = Field(max_length=50)
    price: Optional[Decimal] = Field(default=None, max_digits=12, decimal_places=2)
    construction_date: Optional[date] = None
    energy_class: Optional[str] = Field(default=None, max_length=1)
    energy_class_scheme: Optional[str] = Field(default=None, max_length=20)
    energy_class_date: Optional[date] = None
    energy_kwh_m2: Optional[int] = None
    energy_co2_m2: Optional[int] = None
    latitude: Optional[Decimal] = Field(default=None, max_digits=9, decimal_places=6)
    longitude: Optional[Decimal] = Field(default=None, max_digits=9, decimal_places=6)
    floor: Optional[str] = Field(default=None, max_length=10)
    typology: Optional[str] = Field(default=None, max_length=50)
    nb_rooms: Optional[int] = None
    nb_bedrooms: Optional[int] = None
    nb_bathrooms: Optional[int] = None
    nb_toilets: Optional[int] = None
    nb_swimming_pool: Optional[int] = None
    has_garden: Optional[bool] = None
    nb_balcony: Optional[int] = None
    nb_terrace: Optional[int] = None
    is_climatised: Optional[bool] = None
    surface: Decimal = Field(max_digits=7, decimal_places=2)
    land_surface: Optional[Decimal] = Field(default=None, max_digits=9, decimal_places=2)
    has_cellar: Optional[bool] = None
    has_view: Optional[bool] = None
    is_quiet: Optional[bool] = None
    is_bright: Optional[bool] = None
    has_garage: Optional[bool] = None
    has_elevator: Optional[bool] = None
    has_chimney: Optional[bool] = None
    parking_spaces: Optional[int] = None
    has_separate_kitchen: Optional[bool] = None
    needs_renovation: Optional[bool] = None
    town: str = Field(max_length=100)
    street: Optional[str] = Field(default=None, max_length=100)
    street_number: Optional[str] = Field(default=None, max_length=10)
    postal_code: Optional[str] = Field(default=None, max_length=10)
    information: Optional[str] = None
