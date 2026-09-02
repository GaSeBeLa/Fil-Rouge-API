"""
mandate_model.py — Le mandat de recherche confié à un chasseur par un
client, pour une demande de recherche donnée.
"""

from datetime import date, datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class Mandate(SQLModel, table=True):
    __tablename__ = "mandate"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reference: str = Field(max_length=20, unique=True)
    # status : NOT NULL + CHECK côté base (voir remarque sur typology
    # dans criteria_model.py, même logique).
    status: str = Field(max_length=20)
    signature_date: Optional[date] = None
    signature_type: Optional[str] = Field(default=None, max_length=20)
    ends_at: date
    is_client_signed: bool = False
    is_exclusive: bool
    id_hunter: int = Field(foreign_key="hunter.id_user")
    id_client: int = Field(foreign_key="client.id_user")
    id_search_request: int = Field(foreign_key="search_request.id")
    id_mandate_parent: Optional[int] = Field(default=None, foreign_key="mandate.id")
