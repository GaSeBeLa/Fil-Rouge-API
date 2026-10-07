"""
parameters_fees_model.py — Les honoraires de l'agence : une part fixe et
un taux, en vigueur à partir d'une date.

Une grille vaut jusqu'à la suivante, par construction (Q-SCH-17) : pas de
date de fin, et deux grilles ne démarrent pas le même jour (UNIQUE côté
base). La grille d'une vente = la dernière dont `effective_from` <= la date
de l'acte ; `sale.id_parameters_fees` la désigne (Q-REM-13).

À ne pas confondre avec `commission_scale` : ici c'est ce que l'agence
facture au client ; là-bas c'est ce que l'agence reverse au chasseur.

⚠️ La colonne `hunter.commission_rate` de l'ancienne base (valeurs 2,00 à
3,25) ressemble à un taux d'honoraires de cette table, pas à un taux de
commission. Elle n'a **pas** été migrée tant que le groupe n'a pas
tranché — voir `docker/init-v3/README.md` §3.3.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlmodel import SQLModel, Field


class ParametersFees(SQLModel, table=True):
    __tablename__ = "parameters_fees"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # « En vigueur à partir du » ; UNIQUE côté base (Q-SCH-17).
    effective_from: date
    fixed_amount: int  # euros entiers (INTEGER) : la source donne 3000,00
    # rate : NUMERIC(5,4) — 0.0300 vaut 3 %.
    rate: Decimal = Field(max_digits=5, decimal_places=4)
