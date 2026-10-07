"""
payment_model.py — Le versement dû au chasseur pour une vente, et son
avancement jusqu'au paiement.

Les quatre taux sont conservés **séparément**, pas seulement leur résultat :
c'est ce qui rend un versement explicable après coup.

    base_rate         le taux du barème, selon la tranche de montant
    seniority_rate    la majoration d'ancienneté
    performance_rate  la majoration de performance
    final_rate        le taux réellement appliqué, entre 20 % et 60 %
                      (Q-REM-19) ; exigé dès 'announced' (Q-REM-10)

Avec eux, le score qui a servi (`performance_score`, Q-REM-03) et tous les
termes du calcul (`calculation_details`, Q-REM-04) : un paiement se rejoue
même si les visites ou les ventes changent ensuite.

`amount` est le montant en euros, arrondi **au centime** — l'arrondi exigé
par la règle métier, et impossible dans l'ancienne unité en K€.

Une ligne en statut `refused` (ADR-024) n'est pas un paiement à zero, mais un
**droit ferme** : elle porte son motif, un `amount` a 0, et **aucun** taux ni
bareme. C'est pourquoi les quatre taux et `id_commission_scale` sont
facultatifs ici. La contrainte `chk_refused`, cote base, interdit qu'une ligne
soit un refus a moitie.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field


class Payment(SQLModel, table=True):
    __tablename__ = "payment"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    amount: Decimal = Field(max_digits=12, decimal_places=2)
    # status : NOT NULL + CHECK cote base — 'refused', 'announced',
    # 'scheduled', 'paid'. Les étapes de la facture sont retirées : elle est
    # hors périmètre (Q-JEF-23, Q-REM-17).
    status: str = Field(max_length=20)
    # Une date par étape (Q-REM-17), remplie dès que l'étape est atteinte :
    # chk_announced, chk_scheduled et chk_paid cote base.
    announced_at: Optional[datetime] = None
    scheduled_for: Optional[date] = None
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
    # Score de 0 à 100 qui a servi au calcul (Q-REM-03). NULL sur un refus.
    performance_score: Optional[Decimal] = Field(default=None, max_digits=4, decimal_places=1)
    # Les 5 notes et les entrées du calcul (Q-REM-04), en JSONB cote base.
    calculation_details: Optional[dict[str, Any]] = Field(default=None, sa_type=JSONB)
    id_sale: int = Field(foreign_key="sale.id")
    id_hunter: int = Field(foreign_key="hunter.id_user")
    # NULL sur une ligne de refus : un droit ferme ne designe aucune tranche.
    id_commission_scale: Optional[int] = Field(
        default=None, foreign_key="commission_scale.id"
    )
