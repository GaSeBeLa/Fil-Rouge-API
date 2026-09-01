from pydantic import BaseModel, ConfigDict


class RealEstateManagerBase(BaseModel):
    id_user: int
    company_name: str | None = None


class RealEstateManagerPost(RealEstateManagerBase):
    pass


class RealEstateManagerOut(RealEstateManagerBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class RealEstateManagerPatch(BaseModel):
    company_name: str | None = None