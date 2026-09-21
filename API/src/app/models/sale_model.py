"""
sale_model.py — La vente effectivement signée chez le notaire, au bout
d'un mandat.

C'est la ligne qui déclenche toute la rémunération : `fees_amount` (les
honoraires collectés par le notaire) sert de base au calcul, et
`sale_origin` dit si le chasseur y a droit — une vente `client_alone` est
une vente que le client a conclue seul, hors mandat.

Montants en euros, `NUMERIC(12,2)` : voir `docker/init-v2/README.md` §1.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import SQLModel, Field


class Sale(SQLModel, table=True):
    __tablename__ = "sale"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    signature_date: date
    purchase_amount: Decimal = Field(max_digits=12, decimal_places=2)
    fees_amount: Decimal = Field(max_digits=12, decimal_places=2)
    # sale_origin : NOT NULL + CHECK ('hunter' / 'client_alone') côté base.
    sale_origin: str = Field(max_length=20)
    id_mandate: int = Field(foreign_key="mandate.id")
    id_estate: int = Field(foreign_key="estate.id")
