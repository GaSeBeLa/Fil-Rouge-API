from datetime import date
from pydantic import BaseModel, ConfigDict


class HunterBase(BaseModel):
    id_user: int
    company_name: str | None = None
    education_level: str | None = None
    is_carteT: bool | None = None
    certification_date: date | None = None
    commission_rate: float | None = None


class HunterPost(HunterBase):
    pass


class HunterOut(HunterBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class HunterPatch(BaseModel):
    company_name: str | None = None
    education_level: str | None = None
    is_carteT: bool | None = None
    certification_date: date | None = None
    commission_rate: float | None = None