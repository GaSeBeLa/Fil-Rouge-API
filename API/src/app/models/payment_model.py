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
bareme. C'est pourquoi les quatre taux, `id_commission_scale` et
`id_hunter_rate_parameters` sont facultatifs ici. La contrainte `chk_refused`, cote base, interdit qu'une ligne
soit un refus a moitie.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, Optional

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator
from pydantic import Field as PydanticField
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field
from .input_check import is_input


# --- Le détail du calcul (P32, ADR-033 Décision 2) ---------------------------
#
# Les noms de clés sont fixés ici et recopiés dans ADR-033 (Conséquences) :
# anglais, comme un schéma de données (ADR-002) ; les 5 notes portent les
# noms des colonnes de poids de hunter_rate_parameters. Le service de
# rémunération (API12) traduira les noms de remuneration.py vers ceux-ci.

_Note = Annotated[float, PydanticField(ge=0, le=100)]
_Count = Annotated[int, PydanticField(ge=0)]


class CalculationNotes(BaseModel):
    """Les 5 notes du score, de 0 à 100 (RCR, ADR-033)."""

    model_config = ConfigDict(extra="forbid")

    delay: _Note
    exclusivity: _Note
    sales: _Note
    mandates: _Note
    visits: _Note


class CalculationDetails(BaseModel):
    """
    Ce que `payment.calculation_details` garde d'un calcul (ADR-033) : les 5
    notes et les 4 entrées que rien d'autre ne fige (Décision 2). Les trois
    termes lus sur le mandat (Conséquences) sont facultatifs : le mandat
    reste modifiable, le service les ajoutera au branchement (API12).
    Toute autre clé est refusée : une faute de frappe ne passe pas.
    """

    model_config = ConfigDict(extra="forbid")

    notes: CalculationNotes
    visit_count: _Count
    seniority_years: _Count
    sales_12_months: _Count
    mandates_12_months: _Count
    mandate_signature_date: Optional[date] = None
    mandate_ends_at: Optional[date] = None
    is_exclusive: Optional[bool] = None



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
    # none_as_null : None s'écrit NULL, pas le JSON `null` — sinon chk_refused
    # (ADR-033, Décision 3) croirait un détail présent sur un refus, et vide...
    # jamais hors refus.
    calculation_details: Optional[dict[str, Any]] = Field(
        default=None, sa_type=JSONB(none_as_null=True)  # pyright: ignore[reportArgumentType] -- SQLModel type l'argument en classe ; SQLAlchemy accepte une instance
    )
    id_sale: int = Field(foreign_key="sale.id")
    id_hunter: int = Field(foreign_key="hunter.id_user")
    # NULL sur une ligne de refus : un droit ferme ne designe aucune tranche.
    id_commission_scale: Optional[int] = Field(
        default=None, foreign_key="commission_scale.id"
    )
    # G1 (2026-10-08) : la version des réglages du taux qui a servi au calcul.
    # NULL sur un refus, exigée sinon (chk_refused).
    id_hunter_rate_parameters: Optional[int] = Field(
        default=None, foreign_key="hunter_rate_parameters.id"
    )

    @field_validator("calculation_details")
    @classmethod
    def _details_shape(cls, value: Optional[dict[str, Any]], info: ValidationInfo) -> Optional[dict[str, Any]]:
        """
        P32 : un détail présent a la forme de CalculationDetails (422 sinon) ;
        `{}` ne passe plus. Présent ou absent selon le statut : c'est
        `chk_refused`, côté base (ADR-033, Décision 3), qui le juge.
        """
        if value is None or not is_input(info):
            return value
        # mode="json" : dates en texte ISO, pour la colonne JSONB.
        return CalculationDetails.model_validate(value).model_dump(mode="json", exclude_none=True)
