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

Cohérence d'une version (P29, ADR-053) : contrôlée par l'API à la saisie
(POST, PUT), sans figer aucune valeur — somme des 5 poids = 1, plancher <=
plafond, paliers bien formés. Toujours aucun `CHECK` en base (ADR-034,
Décision 3).

La grille de notes du taux de transformation (Q-JEF-05) n'est pas ici :
elle relève du chantier API.
"""

import math
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.dialects.postgresql import JSONB
from pydantic import ValidationInfo, model_validator
from sqlmodel import SQLModel, Field
from .input_check import is_input


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

    @model_validator(mode="after")
    def _coherent_version(self, info: ValidationInfo) -> "HunterRateParameters":
        """P29 : une version qui ne casse pas le calcul ; refus = 422, à la saisie seulement."""
        if not is_input(info):
            return self
        weights = (
            self.weight_delay,
            self.weight_exclusivity,
            self.weight_sales,
            self.weight_mandates,
            self.weight_visits,
        )
        bounds = (self.rate_floor, self.rate_ceiling)
        # Un modèle de table est construit deux fois : par FastAPI, sans
        # conversion (des textes), puis par `_validated` (crud_router.py),
        # converti. On ne juge que le second passage, qui fait foi.
        if not all(isinstance(value, Decimal) for value in (*weights, *bounds)):
            return self
        # Décimaux exacts : 0.2500 + 0.2000 + ... vaut 1 sans erreur d'arrondi.
        if sum(weights, Decimal(0)) != Decimal(1):
            raise ValueError(f"La somme des 5 poids vaut {sum(weights, Decimal(0))}, pas 1 (P29).")
        if self.rate_floor > self.rate_ceiling:
            raise ValueError(
                f"rate_floor ({self.rate_floor}) dépasse rate_ceiling ({self.rate_ceiling}) (P29)."
            )
        _check_tiers("delay_tiers", self.delay_tiers)
        _check_tiers("visit_tiers", self.visit_tiers)
        return self


def _check_tiers(name: str, tiers: list[dict[str, Any]]) -> None:
    """
    Paliers lus par `note_par_paliers` (services/remuneration.py) : du
    meilleur au moins bon, chacun {"maximum": nombre, "note": nombre}, bornes
    strictement croissantes, le dernier ouvert (`"maximum": null`).
    """
    if not tiers:
        raise ValueError(f"{name} : au moins un palier (P29).")
    previous: Optional[Decimal] = None
    for index, tier in enumerate(tiers):
        if not isinstance(tier, dict) or set(tier) != {"maximum", "note"}:
            raise ValueError(f'{name}[{index}] : il faut exactement les clés "maximum" et "note" (P29).')
        maximum, note = tier["maximum"], tier["note"]
        if not _is_number(note):
            raise ValueError(f"{name}[{index}] : la note doit être un nombre (P29).")
        last = index == len(tiers) - 1
        if last:
            if maximum is not None:
                raise ValueError(f'{name} : le dernier palier doit être ouvert ("maximum": null) (P29).')
            continue
        if not _is_number(maximum):
            raise ValueError(f"{name}[{index}] : seul le dernier palier est ouvert ; maximum doit être un nombre (P29).")
        bound = Decimal(str(maximum))
        if previous is not None and bound <= previous:
            raise ValueError(f"{name} : bornes non croissantes ({previous} puis {bound}) (P29).")
        previous = bound


def _is_number(value: Any) -> bool:
    # bool est un int en Python : on l'écarte exprès. NaN et l'infini aussi :
    # le JSON reçu les accepte, et NaN ne se compare pas (500 au lieu de 422).
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return False
    return math.isfinite(value)
