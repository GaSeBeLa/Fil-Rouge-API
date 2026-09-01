from datetime import date
from pydantic import BaseModel, ConfigDict


class ClientBase(BaseModel):
    id_user: int
    address: str | None = None
    address_complement: str | None = None
    postal_code: str | None = None
    town: str | None = None
    is_married: bool | None = None
    is_civil_solidarity_pact: bool | None = None
    nb_children: int | None = None
    birth_date: date | None = None


class ClientPost(ClientBase):
    pass


class ClientOut(ClientBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ClientPatch(BaseModel):
    address: str | None = None
    address_complement: str | None = None
    postal_code: str | None = None
    town: str | None = None
    is_married: bool | None = None
    is_civil_solidarity_pact: bool | None = None
    nb_children: int | None = None
    birth_date: date | None = None