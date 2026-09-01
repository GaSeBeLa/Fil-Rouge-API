from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict

TypologyType = Literal[
    'Studio', 'T1 / F1', 'T1 bis / F1 bis', 'T2 / F2',
    'T2 bis / F2 bis', 'T3 / F3', 'T3 bis / F3 bis',
    'T4 / F4', 'T4 bis / F4 bis', 'T5 / F5',
    'T5 bis / F5 bis', 'T6+ / F6+'
]


class SearchRequestBase(BaseModel):
    id_author: int
    id_client: int
    id_hunter: int | None = None
    id_realEstateManager: int | None = None


class SearchRequestPost(SearchRequestBase):
    pass


class SearchRequestOut(SearchRequestBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CriteriaBase(BaseModel):
    typology: TypologyType
    budget_min: float
    budget_max: float
    id_author: int
    id_search_request: int
    estate_type: str | None = None
    change_reason: str | None = None
    is_new_build: bool | None = None
    needs_renovation: bool | None = None
    renovation_budget_min: float | None = None
    renovation_budget_max: float | None = None
    energy_kwh_m2_min: int | None = None
    energy_kwh_m2_max: int | None = None
    rooms_min: int | None = None
    rooms_max: int | None = None
    bedrooms_min: int | None = None
    bedrooms_max: int | None = None
    toilets_min: int | None = None
    toilets_max: int | None = None
    swimming_pool_min: int | None = None
    swimming_pool_max: int | None = None
    has_garden: bool | None = None
    nb_balcony_min: int | None = None
    nb_balcony_max: int | None = None
    nb_terrace_min: int | None = None
    nb_terrace_max: int | None = None
    is_climatised: bool | None = None
    surface_min: float | None = None
    surface_max: float | None = None
    land_surface_min: float | None = None
    land_surface_max: float | None = None
    has_separate_kitchen: bool | None = None
    has_garage: bool | None = None
    has_elevator: bool | None = None
    has_chimney: bool | None = None
    parking_spaces: int | None = None
    has_swimming_pool: bool | None = None
    id_previous_version: int | None = None


class CriteriaPost(CriteriaBase):
    pass


class CriteriaOut(CriteriaBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)