from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict

MandateStatus = Literal['active', 'completed', 'expired', 'renewed', 'canceled']
SignatureType = Literal['electronic', 'paper']


class MandateBase(BaseModel):
    reference: str
    status: MandateStatus
    ends_at: date
    is_exclusive: bool
    id_hunter: int
    id_client: int
    id_search_request: int
    is_client_signed: bool = False
    signature_date: date | None = None
    signature_type: SignatureType | None = None
    id_mandate_parent: int | None = None


class MandatePost(MandateBase):
    pass


class MandateOut(MandateBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)