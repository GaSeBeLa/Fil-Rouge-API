"""
visit_model.py — Une visite de bien, faite dans le cadre d'un mandat.

`visitor_type` distingue la visite de repérage du chasseur ('hunter') de
la visite du client ('client') : les deux comptent dans le suivi d'un
mandat, mais elles ne racontent pas la même chose.
"""

from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field


class Visit(SQLModel, table=True):
    __tablename__ = "visit"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    visit_date: date
    # visitor_type : NOT NULL + CHECK cote base — 'hunter' / 'client'.
    visitor_type: str = Field(max_length=10)
    id_estate: int = Field(foreign_key="estate.id")
    id_mandate: int = Field(foreign_key="mandate.id")
