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
Elles sont en euros entiers (`INTEGER`, donc `int`) et **incluses** des deux
côtés (`'[]'` dans 01) : tranches [0 ; 199 999], [200 000 ; 349 999]…
(Q-REM-01, 2026-10-05).
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlmodel import SQLModel, Field


class CommissionScale(SQLModel, table=True):
    __tablename__ = "commission_scale"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    amount_min: int
    # amount_max NULL = derniere tranche, sans plafond.
    amount_max: Optional[int] = None
    # rate : NUMERIC(5,4), un taux, pas un pourcentage — 0.3000 vaut 30 %.
    # > 0 côté base : une tranche à 0 % n'a pas de sens (Q-SCH-15).
    rate: Decimal = Field(max_digits=5, decimal_places=4)
    valid_from: date
    valid_until: Optional[date] = None
    # id_hunter NULL = bareme general ; renseigne = bareme propre a un chasseur.
    id_hunter: Optional[int] = Field(default=None, foreign_key="hunter.id_user")
