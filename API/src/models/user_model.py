from datetime import datetime
from typing import Literal
from pydantic import BaseModel, EmailStr, ConfigDict

CountryIso = Literal['FR', 'ES', 'DE', 'GB', 'IE', 'BE', 'NL', 'LU', 'IT', 'CH']
GenderType = Literal['male', 'female', 'other']


class UserBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone_number: str
    gender: GenderType | None = None
    country_iso: CountryIso | None = None


class UserPost(UserBase):
    password: str


class UserOut(UserBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserPatch(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone_number: str | None = None
    gender: GenderType | None = None
    country_iso: CountryIso | None = None
    password: str | None = None