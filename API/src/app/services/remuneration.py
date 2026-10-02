"""Calcul de la rémunération du chasseur.

Implémentation de référence des règles décrites dans
« documents utiles/REGLES-CALCUL-REMUNERATION.md » et spécifiées dans
« user-stories/10_calcul_remuneration_chasseur.feature ».

============================================================================
COMMENT LIRE CE FICHIER — d'où vient ce code
============================================================================
Ce module n'est PAS écrit par le groupe. C'est le code de référence du
sujet, recopié tel quel, par extraction automatique des huit blocs
`python` de REGLES-CALCUL-REMUNERATION.md (StarterPack - BASE) :
§14.2, lignes 349 à 637 (le calcul), et §14.3, lignes 643 à 687
(`parametrage_par_defaut`). Seule cette docstring est ajoutée.

Pourquoi le reprendre plutôt que le réécrire : c'est la référence que le
sujet rejoue contre le fichier .feature ; une réécriture ne pourrait que
s'en écarter. Les noms restent donc en français, comme dans la source,
pour qu'une comparaison avec elle reste immédiate.

Ce qu'il faut savoir avant de s'en servir :
- fonction PURE : ne lit ni n'écrit en base. Le branchement sur
  commission_scale / parameters_fees / payment est une couche au-dessus,
  pas encore écrite (§14.6).
- les CHIFFRES de `parametrage_par_defaut` (fixe 3 000 €, 2,5 %, tranches,
  poids, bornes) sont des PROPOSITIONS du sujet, pas des règles métier
  (§2, §13) : le groupe peut les changer sans toucher au calcul.
- tests : tests/test_remuneration.py rejoue les 55 cas du .feature.
============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum

CENT = Decimal("0.01")      # rémunération : le centime
TAUX = Decimal("0.0001")    # taux : 0,01 point de %
NOTE = Decimal("0.1")       # score : 1 décimale


def arrondi(valeur: Decimal, precision: Decimal) -> Decimal:
    """Arrondi au demi supérieur (§9). Les trois seuls arrondis du calcul."""
    return valeur.quantize(precision, rounding=ROUND_HALF_UP)


class Exclusivite(Enum):
    EXCLUSIF = "exclusif"
    NON_EXCLUSIF = "non-exclusif"


class OrigineVente(Enum):
    CHASSEUR = "le chasseur"
    CLIENT_SEUL = "le client, en dehors du dispositif"
    AUTRE_AGENCE = "un chasseur d'une autre agence"


class MotifRefus(Enum):
    MANDAT_EXPIRE = "mandat échu à la date de l'acte"
    HORS_DISPOSITIF = "mandat non-exclusif et vente hors dispositif"


@dataclass(frozen=True)
class ParametresHonoraires:
    """Table `parametres_honoraires` : H = F + t × P, daté."""
    date_debut: date
    montant_fixe: Decimal
    taux_pourcentage: Decimal
    date_fin: date | None = None


@dataclass(frozen=True)
class LigneBareme:
    """Une ligne de `baremes_commission` : (chasseur, période, tranche) → taux."""
    date_debut: date
    montant_min: Decimal
    taux: Decimal
    montant_max: Decimal | None = None
    date_fin: date | None = None
    chasseur_id: int | None = None      # None = barème par défaut


@dataclass(frozen=True)
class Palier:
    """Borne haute incluse → note. `maximum=None` = tranche ouverte."""
    maximum: Decimal | None
    note: Decimal


@dataclass(frozen=True)
class ParametresPerformance:
    poids_delai: Decimal
    poids_exclusivite: Decimal
    poids_ventes: Decimal
    poids_mandats: Decimal
    poids_visites: Decimal
    paliers_delai: tuple[Palier, ...]        # en semaines
    paliers_visites: tuple[Palier, ...]
    note_exclusif: Decimal
    note_non_exclusif: Decimal
    points_par_vente: Decimal
    points_par_mandat: Decimal
    fenetre_mois: int = 12


@dataclass(frozen=True)
class ParametresModulation:
    taux_par_annee: Decimal        # a = min(taux_par_annee × années ; plafond)
    plafond_anciennete: Decimal
    score_pivot: Decimal
    demi_amplitude_score: Decimal
    amplitude_performance: Decimal
    taux_plancher: Decimal
    taux_plafond: Decimal


@dataclass(frozen=True)
class Parametrage:
    """L'ensemble des paramètres. Une seule source de vérité."""
    honoraires: tuple[ParametresHonoraires, ...]
    bareme: tuple[LigneBareme, ...]
    performance: ParametresPerformance
    modulation: ParametresModulation


@dataclass(frozen=True)
class Vente:
    chasseur_id: int
    prix_acte: Decimal
    date_acte: date
    date_signature_mandat: date
    date_fin_mandat: date
    exclusivite: Exclusivite
    origine: OrigineVente
    nb_visites: int
    annees_anciennete: int          # années révolues à la date de l'acte
    ventes_12_mois: int             # hors vente en cours
    mandats_12_mois: int


@dataclass(frozen=True)
class Remuneration:
    droit_ouvert: bool
    motif_refus: MotifRefus | None = None
    honoraires: Decimal = Decimal("0.00")
    score_performance: Decimal = Decimal("0.0")
    notes: dict[str, Decimal] = field(default_factory=dict)
    taux_base: Decimal = Decimal("0")
    majoration_anciennete: Decimal = Decimal("0")
    modulation_performance: Decimal = Decimal("0")
    taux_final: Decimal = Decimal("0")
    montant: Decimal = Decimal("0.00")

    @property
    def marge_entreprise(self) -> Decimal:
        """Jamais arrondie séparément (§9) : simple différence."""
        return self.honoraires - self.montant


class BaremeIntrouvable(Exception):
    """Aucune ligne applicable : erreur de paramétrage, pas un cas métier."""


def droit_a_remuneration(vente: Vente) -> MotifRefus | None:
    """Retourne le motif de refus, ou None si le droit est ouvert."""
    if vente.date_acte > vente.date_fin_mandat:
        return MotifRefus.MANDAT_EXPIRE
    if vente.exclusivite is Exclusivite.EXCLUSIF:
        return None                            # payé même si le client trouve seul
    if vente.origine is OrigineVente.CHASSEUR:
        return None
    return MotifRefus.HORS_DISPOSITIF


def parametres_honoraires_applicables(
    parametrage: Parametrage, date_acte: date
) -> ParametresHonoraires:
    for p in parametrage.honoraires:
        if p.date_debut <= date_acte and (p.date_fin is None or date_acte <= p.date_fin):
            return p
    raise BaremeIntrouvable(f"aucun paramètre d'honoraires au {date_acte}")


def calculer_honoraires(prix: Decimal, p: ParametresHonoraires) -> Decimal:
    """H = F + t × P."""
    return arrondi(p.montant_fixe + p.taux_pourcentage * prix, CENT)


def note_par_paliers(valeur: Decimal, paliers: tuple[Palier, ...]) -> Decimal:
    """Paliers ordonnés du meilleur au moins bon ; le dernier est ouvert."""
    for palier in paliers:
        if palier.maximum is None or valeur <= palier.maximum:
            return palier.note
    return Decimal(0)


def semaines_ecoulees(debut: date, fin: date) -> int:
    """Délai mandat → acte, arrondi à la semaine inférieure (règle métier)."""
    return (fin - debut).days // 7


def noter_criteres(vente: Vente, p: ParametresPerformance) -> dict[str, Decimal]:
    semaines = Decimal(semaines_ecoulees(vente.date_signature_mandat, vente.date_acte))
    return {
        "delai": note_par_paliers(semaines, p.paliers_delai),
        "exclusivite": (
            p.note_exclusif
            if vente.exclusivite is Exclusivite.EXCLUSIF
            else p.note_non_exclusif
        ),
        "ventes": min(Decimal(100), Decimal(vente.ventes_12_mois) * p.points_par_vente),
        "mandats": min(Decimal(100), Decimal(vente.mandats_12_mois) * p.points_par_mandat),
        "visites": note_par_paliers(Decimal(vente.nb_visites), p.paliers_visites),
    }


def calculer_score(notes: dict[str, Decimal], p: ParametresPerformance) -> Decimal:
    poids = {
        "delai": p.poids_delai,
        "exclusivite": p.poids_exclusivite,
        "ventes": p.poids_ventes,
        "mandats": p.poids_mandats,
        "visites": p.poids_visites,
    }
    return arrondi(sum((notes[c] * poids[c] for c in poids), Decimal(0)), NOTE)


def taux_de_tranche(
    parametrage: Parametrage, chasseur_id: int, date_acte: date, prix: Decimal
) -> Decimal:
    """Transcription de la requête SQL du §7 : le nominatif prime sur le défaut."""
    lignes = [
        l
        for l in parametrage.bareme
        if l.chasseur_id in (chasseur_id, None)
        and l.date_debut <= date_acte
        and (l.date_fin is None or date_acte <= l.date_fin)
        and l.montant_min <= prix
        and (l.montant_max is None or prix <= l.montant_max)
    ]
    if not lignes:
        raise BaremeIntrouvable(
            f"aucun barème pour le chasseur {chasseur_id}, {prix} € au {date_acte}"
        )
    lignes.sort(key=lambda l: (l.chasseur_id is not None, l.date_debut), reverse=True)
    return lignes[0].taux


def majoration_anciennete(annees: int, p: ParametresModulation) -> Decimal:
    return min(p.taux_par_annee * Decimal(annees), p.plafond_anciennete)


def modulation_performance(score: Decimal, p: ParametresModulation) -> Decimal:
    return (score - p.score_pivot) / p.demi_amplitude_score * p.amplitude_performance


def taux_final(
    taux_base: Decimal, a: Decimal, pf: Decimal, p: ParametresModulation
) -> Decimal:
    """Variations relatives, additionnées avant application, puis bornées."""
    brut = taux_base * (Decimal(1) + a + pf)
    return arrondi(min(max(brut, p.taux_plancher), p.taux_plafond), TAUX)


def calculer_remuneration(vente: Vente, parametrage: Parametrage) -> Remuneration:
    motif = droit_a_remuneration(vente)
    if motif is not None:
        return Remuneration(droit_ouvert=False, motif_refus=motif)

    honoraires = calculer_honoraires(
        vente.prix_acte, parametres_honoraires_applicables(parametrage, vente.date_acte)
    )
    notes = noter_criteres(vente, parametrage.performance)
    score = calculer_score(notes, parametrage.performance)

    r0 = taux_de_tranche(parametrage, vente.chasseur_id, vente.date_acte, vente.prix_acte)
    a = majoration_anciennete(vente.annees_anciennete, parametrage.modulation)
    pf = modulation_performance(score, parametrage.modulation)
    r = taux_final(r0, a, pf, parametrage.modulation)

    return Remuneration(
        droit_ouvert=True,
        honoraires=honoraires,
        score_performance=score,
        notes=notes,
        taux_base=r0,
        majoration_anciennete=a,
        modulation_performance=pf,
        taux_final=r,
        montant=arrondi(r * honoraires, CENT),
    )


def parametrage_par_defaut() -> Parametrage:
    d = Decimal
    debut = date(2026, 1, 1)
    return Parametrage(
        honoraires=(
            ParametresHonoraires(debut, d("3000.00"), d("0.025")),          # D1
        ),
        bareme=(
            LigneBareme(debut, d(0), d("0.30"), d(199999)),                 # D3
            LigneBareme(debut, d(200000), d("0.35"), d(349999)),
            LigneBareme(debut, d(350000), d("0.40"), d(499999)),
            LigneBareme(debut, d(500000), d("0.45"), d(749999)),
            LigneBareme(debut, d(750000), d("0.50")),
        ),
        performance=ParametresPerformance(                                  # D6
            poids_delai=d("0.25"),
            poids_exclusivite=d("0.10"),
            poids_ventes=d("0.25"),
            poids_mandats=d("0.15"),
            poids_visites=d("0.25"),
            paliers_delai=(
                Palier(d(12), d(100)), Palier(d(20), d(80)), Palier(d(28), d(60)),
                Palier(d(36), d(40)), Palier(d(48), d(20)), Palier(None, d(0)),
            ),
            paliers_visites=(
                Palier(d(3), d(100)), Palier(d(6), d(80)), Palier(d(9), d(60)),
                Palier(d(12), d(40)), Palier(d(15), d(20)), Palier(None, d(0)),
            ),
            note_exclusif=d(100),
            note_non_exclusif=d(60),
            points_par_vente=d(20),
            points_par_mandat=d(10),
        ),
        modulation=ParametresModulation(                                    # D7
            taux_par_annee=d("0.02"),
            plafond_anciennete=d("0.10"),
            score_pivot=d(50),
            demi_amplitude_score=d(50),
            amplitude_performance=d("0.20"),
            taux_plancher=d("0.20"),                                        # D8
            taux_plafond=d("0.60"),
        ),
    )
