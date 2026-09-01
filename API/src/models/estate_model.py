from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict

EstateType = Literal[
    'Appartement', 'Maison', 'Studio', 'Loft', 'Villa',
    'Duplex', 'Terrain', 'Local commercial', 'Chalet', 'Château'
]


class PictureBase(BaseModel):
    url: str | None = None
    id_estate: int


class PictureOut(PictureBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EstateBase(BaseModel):
    reference: str
    estate_type: EstateType
    surface: float
    town: str
    price: float | None = None
    construction_date: date | None = None
    latitude: float | None = None
    longitude: float | None = None
    nb_floors: int | None = None
    nb_rooms: int | None = None
    nb_bedrooms: int | None = None
    nb_bathrooms: int | None = None
    nb_toilets: int | None = None
    nb_swimming_pool: int | None = None
    has_garden: bool | None = None
    nb_balcony: int | None = None
    nb_terrace: int | None = None
    is_climatised: bool | None = None
    energetic_score: int | None = None
    land_surface: float | None = None
    has_garage: bool | None = None
    has_elevator: bool | None = None
    has_chimney: bool | None = None
    parking_spaces: int | None = None
    has_separate_kitchen: bool | None = None
    needs_renovation: bool | None = None
    street: str | None = None
    street_number: str | None = None
    postal_code: str | None = None
    information: str | None = None


class EstatePost(EstateBase):
    pass


class EstateOut(EstateBase):
    id: int
    created_at: datetime
    pictures: list[PictureOut] = []

    model_config = ConfigDict(from_attributes=True)


class EstatePatch(BaseModel):
    reference: str | None = None
    estate_type: EstateType | None = None
    surface: float | None = None
    town: str | None = None
    price: float | None = None
    construction_date: date | None = None
    latitude: float | None = None
    longitude: float | None = None
    nb_floors: int | None = None
    nb_rooms: int | None = None
    nb_bedrooms: int | None = None
    nb_bathrooms: int | None = None
    nb_toilets: int | None = None
    nb_swimming_pool: int | None = None
    has_garden: bool | None = None
    nb_balcony: int | None = None
    nb_terrace: int | None = None
    is_climatised: bool | None = None
    energetic_score: int | None = None
    land_surface: float | None = None
    has_garage: bool | None = None
    has_elevator: bool | None = None
    has_chimney: bool | None = None
    parking_spaces: int | None = None
    has_separate_kitchen: bool | None = None
    needs_renovation: bool | None = None
    street: str | None = None
    street_number: str | None = None
    postal_code: str | None = None
    information: str | None = None