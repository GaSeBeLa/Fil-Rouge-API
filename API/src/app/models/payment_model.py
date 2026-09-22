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

Une ligne en statut `refused` (ADR-024) n'est pas un paiement à zero, mais un
**droit ferme** : elle porte son motif, un `amount` a 0, et **aucun** taux ni
bareme. C'est pourquoi les quatre taux et `id_commission_scale` sont
facultatifs ici. La contrainte `chk_refused`, cote base, interdit qu'une ligne
soit un refus a moitie.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlmodel import SQLModel, Field


class Payment(SQLModel, table=True):
    __tablename__ = "payment"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    amount: Decimal = Field(max_digits=12, decimal_places=2)
    # status : NOT NULL + CHECK cote base — 'refused', 'announced',
    # 'invoice_submitted', 'verified', 'scheduled', 'paid'.
    status: str = Field(max_length=20)
    paid_at: Optional[datetime] = None
    # Motif du droit refuse (ADR-024) : 'mandate_expired' ou 'out_of_scope'.
    # Renseigne si et seulement si status vaut 'refused'.
    refusal_reason: Optional[str] = Field(default=None, max_length=30)
    # Les taux sont des NUMERIC(5,4) : 0.3000 vaut 30 %.
    # Tous NULL sur une ligne de refus (contrainte chk_refused).
    base_rate: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=4)
    final_rate: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=4)
    seniority_rate: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=4)
    performance_rate: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=4)
    id_sale: int = Field(foreign_key="sale.id")
    id_hunter: int = Field(foreign_key="hunter.id_user")
    # NULL sur une ligne de refus : un droit ferme ne designe aucune tranche.
    id_commission_scale: Optional[int] = Field(
        default=None, foreign_key="commission_scale.id"
    )
