"""
criteria_model.py — Les critères de recherche structurés, rattachés à
une demande de recherche (search_request). Une nouvelle version de
critères peut référencer la précédente via id_previous_version.
"""

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class Criteria(SQLModel, table=True):
    __tablename__ = "criteria"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    change_reason: Optional[str] = Field(default=None, max_length=255)
    estate_type: Optional[str] = Field(default=None, max_length=50)
    # typology : NOT NULL + CHECK côté base (liste fermée de valeurs T1-T6+).
    # SQLModel ne réplique pas ce CHECK ici — c'est PostgreSQL qui le
    # fera respecter à l'insertion. Une valeur hors liste sera rejetée par
    # la base, pas avant, avec une erreur PostgreSQL (pas une erreur
    # Pydantic "propre"). À améliorer plus tard si besoin (voir le
    # docstring du package dans __init__.py).
    typology: str = Field(max_length=50)
    # floor n'est plus NOT NULL côté base (retiré du schéma) : optionnel ici aussi.
    floor: Optional[str] = Field(default=None, max_length=10)
    budget_min: float
    budget_max: float
    is_new_build: Optional[bool] = None
    needs_renovation: Optional[bool] = None
    renovation_budget_min: Optional[float] = None
    renovation_budget_max: Optional[float] = None
    energy_kwh_m2_min: Optional[int] = None
    energy_kwh_m2_max: Optional[int] = None
    rooms_min: Optional[int] = None
    rooms_max: Optional[int] = None
    bedrooms_min: Optional[int] = None
    bedrooms_max: Optional[int] = None
    toilets_min: Optional[int] = None
    toilets_max: Optional[int] = None
    swimming_pool_min: Optional[int] = None
    swimming_pool_max: Optional[int] = None
    has_garden: Optional[bool] = None
    nb_balcony_min: Optional[int] = None
    nb_balcony_max: Optional[int] = None
    nb_terrace_min: Optional[int] = None
    nb_terrace_max: Optional[int] = None
    is_climatised: Optional[bool] = None
    surface_min: Optional[float] = None
    surface_max: Optional[float] = None
    land_surface_min: Optional[float] = None
    land_surface_max: Optional[float] = None
    has_separate_kitchen: Optional[bool] = None
    has_cellar: Optional[bool] = None
    has_view: Optional[bool] = None
    is_quiet: Optional[bool] = None
    is_bright: Optional[bool] = None
    has_garage: Optional[bool] = None
    has_elevator: Optional[bool] = None
    has_chimney: Optional[bool] = None
    parking_spaces: Optional[int] = None
    has_swimming_pool: Optional[bool] = None
    id_author: int = Field(foreign_key="user.id")
    id_search_request: int = Field(foreign_key="search_request.id")
    id_previous_version: Optional[int] = Field(default=None, foreign_key="criteria.id")
