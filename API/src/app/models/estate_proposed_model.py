"""
estate_proposed_model.py — Un bien proposé par un chasseur pour un
mandat donné, avec le retour du client (montant proposé, acceptation).
"""

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class EstateProposed(SQLModel, table=True):
    __tablename__ = "estate_proposed"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    comment_hunter: Optional[str] = None
    comment_client: Optional[str] = None
    amount_proposition: Optional[float] = None
    is_accepted: Optional[bool] = None
    id_hunter: int = Field(foreign_key="hunter.id_user")
    id_estate: int = Field(foreign_key="estate.id")
    id_mandate: int = Field(foreign_key="mandate.id")
