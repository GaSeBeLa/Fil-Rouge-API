from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict

MediaType = Literal['audio', 'video']


class EstateSearchRequestBase(BaseModel):
    media_type: MediaType
    id_estate: int
    id_search_request: int
    id_hunter: int
    review_hunter: str | None = None
    media_url: str | None = None


class EstateSearchRequestPost(EstateSearchRequestBase):
    pass


class EstateSearchRequestOut(EstateSearchRequestBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)