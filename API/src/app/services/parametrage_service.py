"""
parametrage_service.py — Lit les trois tables de paramètres et en fait le
`Parametrage` que le calcul de rémunération attend.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Le calcul (`remuneration.py`) est une fonction pure : il reçoit un
`Parametrage` et ne touche pas à la base. Le sujet veut ses valeurs « dans
une table de paramètres, jamais en dur » (REGLES-CALCUL-REMUNERATION.md l. 47)
et le calcul « isolé du paramétrage » (§14.3). Ce service est le pont : il lit

    parameters_fees         -> Parametrage.honoraires
    commission_scale        -> Parametrage.bareme
    hunter_rate_parameters  -> Parametrage.performance et .modulation

Il ne calcule rien et n'écrit rien. Comme les autres services, il ne parle
qu'à des repositories, jamais à la Session directement.

Versions (Q-SCH-17, Q-REM-05) : une version vaut jusqu'à la suivante, sans
date de fin en base. Le calcul, lui, lit une date de fin : le service la
déduit (la veille de la version suivante). Honoraires et barème sont rendus
en entier, le calcul choisit selon la date de l'acte. Les réglages du taux,
eux, n'ont qu'UNE version dans un `Parametrage` : le service prend celle en
vigueur à la date demandée.

Qui ferme la boucle : `reglages_applicables` rend la ligne choisie, donc son
`id` — celui que `payment.id_hunter_rate_parameters` doit garder pour que le
calcul reste explicable plus tard (REGLES-CALCUL-REMUNERATION.md l. 281-292).

Pas encore branché sur une route : aucun endpoint ne calcule de paiement
aujourd'hui.
============================================================================
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlmodel import Session

from ..models import CommissionScale, HunterRateParameters, ParametersFees
from ..repositories.commission_scale_repository import CommissionScaleRepository
from ..repositories.hunter_rate_parameters_repository import HunterRateParametersRepository
from ..repositories.parameters_fees_repository import ParametersFeesRepository
from .remuneration import (
    BaremeIntrouvable,
    LigneBareme,
    Palier,
    Parametrage,
    ParametresHonoraires,
    ParametresModulation,
    ParametresPerformance,
)


def _paliers(raw: list[dict[str, Any]]) -> tuple[Palier, ...]:
    """JSONB `[{"maximum": 12, "note": 100}, ...]` -> paliers, dans l'ordre de la base."""
    return tuple(
        Palier(None if p["maximum"] is None else Decimal(str(p["maximum"])), Decimal(str(p["note"])))
        for p in raw
    )


def _honoraires(fees: list[ParametersFees]) -> tuple[ParametresHonoraires, ...]:
    """Une version vaut jusqu'à la veille de la suivante ; la dernière est ouverte."""
    ordered = sorted(fees, key=lambda f: f.effective_from)
    result: list[ParametresHonoraires] = []
    for i, fee in enumerate(ordered):
        following = ordered[i + 1].effective_from if i + 1 < len(ordered) else None
        result.append(
            ParametresHonoraires(
                date_debut=fee.effective_from,
                montant_fixe=Decimal(fee.fixed_amount),
                taux_pourcentage=fee.rate,
                date_fin=None if following is None else following - timedelta(days=1),
            )
        )
    return tuple(result)


def _bareme(scale: list[CommissionScale]) -> tuple[LigneBareme, ...]:
    return tuple(
        LigneBareme(
            date_debut=line.valid_from,
            montant_min=Decimal(line.amount_min),
            taux=line.rate,
            montant_max=None if line.amount_max is None else Decimal(line.amount_max),
            date_fin=line.valid_until,
            chasseur_id=line.id_hunter,
        )
        for line in sorted(scale, key=lambda s: (s.valid_from, s.id_hunter is not None, s.amount_min))
    )


def _performance(r: HunterRateParameters) -> ParametresPerformance:
    return ParametresPerformance(
        poids_delai=r.weight_delay,
        poids_exclusivite=r.weight_exclusivity,
        poids_ventes=r.weight_sales,
        poids_mandats=r.weight_mandates,
        poids_visites=r.weight_visits,
        paliers_delai=_paliers(r.delay_tiers),
        paliers_visites=_paliers(r.visit_tiers),
        note_exclusif=r.score_exclusive,
        note_non_exclusif=r.score_non_exclusive,
        points_par_vente=r.points_per_sale,
        points_par_mandat=r.points_per_mandate,
        fenetre_mois=r.window_months,
    )


def _modulation(r: HunterRateParameters) -> ParametresModulation:
    return ParametresModulation(
        taux_par_annee=r.seniority_rate_per_year,
        plafond_anciennete=r.seniority_cap,
        score_pivot=r.score_pivot,
        demi_amplitude_score=r.score_half_range,
        amplitude_performance=r.performance_amplitude,
        taux_plancher=r.rate_floor,
        taux_plafond=r.rate_ceiling,
    )


class ParametrageService:
    def __init__(
        self,
        fees_repository: ParametersFeesRepository,
        scale_repository: CommissionScaleRepository,
        rate_repository: HunterRateParametersRepository,
    ):
        self.fees_repository = fees_repository
        self.scale_repository = scale_repository
        self.rate_repository = rate_repository

    def reglages_applicables(self, session: Session, a_la_date: date) -> HunterRateParameters:
        """La version des réglages du taux en vigueur à `a_la_date` (la dernière démarrée).

        Lève `BaremeIntrouvable` s'il n'y en a aucune : erreur de paramétrage
        (table vide, ou date antérieure à la première version), pas un cas métier.
        """
        started = [r for r in self.rate_repository.list_all(session) if r.effective_from <= a_la_date]
        if not started:
            raise BaremeIntrouvable(f"aucun réglage du taux du chasseur au {a_la_date}")
        return max(started, key=lambda r: r.effective_from)

    def charger(self, session: Session, a_la_date: date) -> Parametrage:
        """Le `Parametrage` à donner à `calculer_remuneration` pour un acte daté `a_la_date`."""
        reglages = self.reglages_applicables(session, a_la_date)
        return Parametrage(
            honoraires=_honoraires(self.fees_repository.list_all(session)),
            bareme=_bareme(self.scale_repository.list_all(session)),
            performance=_performance(reglages),
            modulation=_modulation(reglages),
        )
