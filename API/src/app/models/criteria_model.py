"""
criteria_model.py — Les critères de recherche structurés, rattachés à une
demande de recherche (search_request). Une nouvelle version de critères
peut référencer la précédente via `id_previous_version`.

Les budgets sont en euros, `NUMERIC(12,2)` — donc `Decimal`, pas `float`
(voir `docker/init-v2/README.md` §1).

Attention au sens des contraintes, qui n'est pas celui qu'on devine :
`estate_type` et `budget_max` sont **obligatoires**, tandis que `typology`
et `budget_min` sont facultatifs.

Les colonnes à liste fermée (`estate_type`, `typology`, `floor`,
`energy_class_max`, `country_iso`) portent un CHECK côté base.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import SQLModel, Field


class Criteria(SQLModel, table=True):
    __tablename__ = "criteria"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    change_reason: Optional[str] = Field(default=None, max_length=255)
    country_iso: Optional[str] = Field(default=None, max_length=2)
    town: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=10)
    estate_type: str = Field(max_length=50)
    typology: Optional[str] = Field(default=None, max_length=50)
    budget_min: Optional[Decimal] = Field(default=None, max_digits=12, decimal_places=2)
    budget_max: Decimal = Field(max_digits=12, decimal_places=2)
    floor: Optional[str] = Field(default=None, max_length=10)
    is_new_build: Optional[bool] = None
    needs_renovation: Optional[bool] = None
    renovation_budget_min: Optional[Decimal] = Field(default=None, max_digits=12, decimal_places=2)
    renovation_budget_max: Optional[Decimal] = Field(default=None, max_digits=12, decimal_places=2)
    energy_class_max: Optional[str] = Field(default=None, max_length=1)
    rooms_min: Optional[int] = None
    rooms_max: Optional[int] = None
    bedrooms_min: Optional[int] = None
    bedrooms_max: Optional[int] = None
    toilets_min: Optional[int] = None
    toilets_max: Optional[int] = None
    bathrooms_min: Optional[int] = None
    bathrooms_max: Optional[int] = None
    swimming_pool_min: Optional[int] = None
    swimming_pool_max: Optional[int] = None
    has_garden: Optional[bool] = None
    nb_balcony_min: Optional[int] = None
    nb_balcony_max: Optional[int] = None
    nb_terrace_min: Optional[int] = None
    nb_terrace_max: Optional[int] = None
    is_climatised: Optional[bool] = None
    surface_min: Optional[Decimal] = Field(default=None, max_digits=7, decimal_places=2)
    surface_max: Optional[Decimal] = Field(default=None, max_digits=7, decimal_places=2)
    land_surface_min: Optional[Decimal] = Field(default=None, max_digits=9, decimal_places=2)
    land_surface_max: Optional[Decimal] = Field(default=None, max_digits=9, decimal_places=2)
    has_separate_kitchen: Optional[bool] = None
    has_cellar: Optional[bool] = None
    has_view: Optional[bool] = None
    is_quiet: Optional[bool] = None
    is_bright: Optional[bool] = None
    has_garage: Optional[bool] = None
    has_elevator: Optional[bool] = None
    has_chimney: Optional[bool] = None
    parking_spaces: Optional[int] = None
    id_author: int = Field(foreign_key="user.id")
    id_search_request: int = Field(foreign_key="search_request.id")
    id_previous_version: Optional[int] = Field(default=None, foreign_key="criteria.id")
