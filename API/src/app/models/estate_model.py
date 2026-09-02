"""
estate_model.py — Les biens immobiliers (annonces) proposés aux
clients.
"""

from datetime import date, datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class Estate(SQLModel, table=True):
    __tablename__ = "estate"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reference: str = Field(max_length=50, unique=True)
    estate_type: str = Field(max_length=50)  # NOT NULL + CHECK côté base
    price: Optional[float] = None
    construction_date: Optional[date] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # floor n'est plus NOT NULL côté base (retiré du schéma) : optionnel ici aussi.
    floor: Optional[str] = Field(default=None, max_length=10)  # CHECK côté base
    nb_rooms: Optional[int] = None
    nb_bedrooms: Optional[int] = None
    nb_bathrooms: Optional[int] = None
    nb_toilets: Optional[int] = None
    nb_swimming_pool: Optional[int] = None
    has_garden: Optional[bool] = None
    nb_balcony: Optional[int] = None
    nb_terrace: Optional[int] = None
    is_climatised: Optional[bool] = None
    energetic_score: Optional[int] = None
    surface: float
    land_surface: Optional[float] = None
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
