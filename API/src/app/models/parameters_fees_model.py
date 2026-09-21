"""
parameters_fees_model.py — Les honoraires de l'agence : une part fixe et
un taux, valables sur une période.

À ne pas confondre avec `commission_scale` : ici c'est ce que l'agence
facture au client ; là-bas c'est ce que l'agence reverse au chasseur.

⚠️ La colonne `hunter.commission_rate` de l'ancienne base (valeurs 2,00 à
3,25) ressemble à un taux d'honoraires de cette table, pas à un taux de
commission. Elle n'a **pas** été migrée tant que le groupe n'a pas
tranché — voir `docker/init-v2/README.md` §3.3.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import SQLModel, Field


class ParametersFees(SQLModel, table=True):
    __tablename__ = "parameters_fees"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    valid_from: date
    valid_until: Optional[date] = None
    fixed_amount: Decimal = Field(max_digits=12, decimal_places=2)
    # rate : NUMERIC(5,4) — 0.0300 vaut 3 %.
    rate: Decimal = Field(max_digits=5, decimal_places=4)
