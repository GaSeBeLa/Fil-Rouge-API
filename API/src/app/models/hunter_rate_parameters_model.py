"""
hunter_rate_parameters_model.py — Les réglages du taux du chasseur : tout ce
qui fait passer du taux du barème au taux final — poids, paliers, notes et
points de la performance, effets de l'ancienneté et de la performance, bornes
du taux final.

Nommée `remuneration_parameters` jusqu'au 2026-10-08 : renommée (G2) parce
que le nom se confondait avec `parameters_fees`, les honoraires de l'agence.

Le sujet veut ces valeurs « dans une table de paramètres, jamais en dur »
(REGLES-CALCUL-REMUNERATION.md l. 47 ; Q-REM-05). Une ligne = un jeu
complet : les champs de `ParametresPerformance` et `ParametresModulation`
(services/remuneration.py, l. 92-116), noms traduits en anglais. Les
honoraires et le barème ont leurs propres tables (`parameters_fees`,
`commission_scale`).

Une version vaut jusqu'à la suivante, comme `parameters_fees` (Q-SCH-17,
retenu pour cette table le 2026-10-07) : deux versions ne démarrent pas le
même jour (UNIQUE côté base). Aucune borne sur les valeurs : ce sont des
paramètres « à valider avec le client » (l. 59).

La grille de notes du taux de transformation (Q-JEF-05) n'est pas ici :
elle relève du chantier API.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field


class HunterRateParameters(SQLModel, table=True):
    __tablename__ = "hunter_rate_parameters"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # « En vigueur à partir du » ; UNIQUE côté base.
    effective_from: date

    # Performance — poids des 5 critères, NUMERIC(5,4) : 0.2500 vaut 25 %.
    weight_delay: Decimal = Field(max_digits=5, decimal_places=4)
    weight_exclusivity: Decimal = Field(max_digits=5, decimal_places=4)
    weight_sales: Decimal = Field(max_digits=5, decimal_places=4)
    weight_mandates: Decimal = Field(max_digits=5, decimal_places=4)
    weight_visits: Decimal = Field(max_digits=5, decimal_places=4)
    # Paliers en JSONB, borne haute incluse -> note, la dernière ouverte :
    # [{"maximum": 12, "note": 100}, ..., {"maximum": None, "note": 0}].
    delay_tiers: list[dict[str, Any]] = Field(sa_type=JSONB)  # en semaines
    visit_tiers: list[dict[str, Any]] = Field(sa_type=JSONB)
    # Notes et points, NUMERIC(4,1), même domaine que les scores.
    score_exclusive: Decimal = Field(max_digits=4, decimal_places=1)
    score_non_exclusive: Decimal = Field(max_digits=4, decimal_places=1)
    points_per_sale: Decimal = Field(max_digits=4, decimal_places=1)
    points_per_mandate: Decimal = Field(max_digits=4, decimal_places=1)
    window_months: int

    # Modulation — a = min(taux × années ; plafond),
    # p = (S - pivot) / demi-amplitude × amplitude, puis r borné.
    seniority_rate_per_year: Decimal = Field(max_digits=5, decimal_places=4)
    seniority_cap: Decimal = Field(max_digits=5, decimal_places=4)
    score_pivot: Decimal = Field(max_digits=4, decimal_places=1)
    score_half_range: Decimal = Field(max_digits=4, decimal_places=1)
    performance_amplitude: Decimal = Field(max_digits=5, decimal_places=4)
    rate_floor: Decimal = Field(max_digits=5, decimal_places=4)
    rate_ceiling: Decimal = Field(max_digits=5, decimal_places=4)
