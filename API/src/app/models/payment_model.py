"""
payment_model.py — Le versement dû au chasseur pour une vente, et son
avancement jusqu'au paiement.

Les quatre taux sont conservés **séparément**, pas seulement leur résultat :
c'est ce qui rend un versement explicable après coup.

    base_rate         le taux du barème, selon la tranche de montant
    seniority_rate    la majoration d'ancienneté
    performance_rate  la majoration de performance
    final_rate        le taux réellement applique (NULL tant qu'il n'est
                      pas arrête)

`amount` est le montant en euros, arrondi **au centime** — l'arrondi exigé
par la règle métier, et impossible dans l'ancienne unité en K€.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import SQLModel, Field


class Payment(SQLModel, table=True):
    __tablename__ = "payment"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    amount: Decimal = Field(max_digits=12, decimal_places=2)
    # status : NOT NULL + CHECK cote base — 'announced', 'invoice_submitted',
    # 'verified', 'scheduled', 'paid'.
    status: str = Field(max_length=20)
    paid_at: Optional[datetime] = None
    # Les taux sont des NUMERIC(5,4) : 0.3000 vaut 30 %.
    base_rate: Decimal = Field(max_digits=5, decimal_places=4)
    final_rate: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=4)
    seniority_rate: Decimal = Field(max_digits=5, decimal_places=4)
    performance_rate: Decimal = Field(max_digits=5, decimal_places=4)
    id_sale: int = Field(foreign_key="sale.id")
    id_hunter: int = Field(foreign_key="hunter.id_user")
    id_commission_scale: int = Field(foreign_key="commission_scale.id")
