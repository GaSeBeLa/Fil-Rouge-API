"""
commission_scale_model.py — Le barème de rémunération du chasseur : une
tranche de montant, un taux, une période de validité.

Le barème officiel vit dans
`user-stories/10_calcul_remuneration_chasseur.feature` (l. 22-27) : 30 %
jusqu'à 199 999 €, puis 35 %, 40 %, 45 %, et 50 % au-delà de 750 000 €.

Deux choses à savoir :

- `amount_max` est `NULL` pour la dernière tranche (« et au-delà »).
- `id_hunter` est `NULL` pour le barème général ; renseigné, la ligne est
  un barème propre à un chasseur.

Les bornes sont **à l'euro près** — c'est la raison même du passage aux
euros : en K€ au dixième, 199 999 € basculait dans la tranche à 35 %.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlmodel import SQLModel, Field


class CommissionScale(SQLModel, table=True):
    __tablename__ = "commission_scale"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    amount_min: Decimal = Field(max_digits=12, decimal_places=2)
    # amount_max NULL = derniere tranche, sans plafond.
    amount_max: Optional[Decimal] = Field(default=None, max_digits=12, decimal_places=2)
    # rate : NUMERIC(5,4), un taux, pas un pourcentage — 0.3000 vaut 30 %.
    rate: Decimal = Field(max_digits=5, decimal_places=4)
    valid_from: date
    valid_until: Optional[date] = None
    # id_hunter NULL = bareme general ; renseigne = bareme propre a un chasseur.
    id_hunter: Optional[int] = Field(default=None, foreign_key="hunter.id_user")
