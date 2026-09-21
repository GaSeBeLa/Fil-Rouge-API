"""
hunter_performance_model.py — Le score de performance d'un chasseur, daté,
et ce qui l'a déclenché.

La table garde un **historique** : chaque score vaut sur une période
(`valid_from` / `valid_until`), au lieu d'écraser le précédent. C'est ce
qui permet de rejouer un calcul de rémunération tel qu'il était au moment
de la vente.

`trigger_type` dit d'où vient la ligne :

    initial           le score de départ, à l'embauche
    payment           recalculé à la suite d'un versement
    mandate_expired   recalculé parce qu'un mandat s'est éteint sans vente

`id_payment` et `id_mandate` sont donc `NULL` selon le déclencheur.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import SQLModel, Field


class HunterPerformance(SQLModel, table=True):
    __tablename__ = "hunter_performance"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # score : NUMERIC(4,1).
    score: Decimal = Field(max_digits=4, decimal_places=1)
    valid_from: date
    valid_until: Optional[date] = None
    # trigger_type : NOT NULL + CHECK cote base — 'initial', 'payment',
    # 'mandate_expired'.
    trigger_type: str = Field(max_length=20)
    id_hunter: int = Field(foreign_key="hunter.id_user")
    # Renseigne selon le declencheur, NULL sinon.
    id_payment: Optional[int] = Field(default=None, foreign_key="payment.id")
    id_mandate: Optional[int] = Field(default=None, foreign_key="mandate.id")
