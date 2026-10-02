"""
test_remuneration.py — Les 55 cas de 10_calcul_remuneration_chasseur.feature.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Un bloc par `Règle:` du fichier user-stories/10_calcul_remuneration_chasseur.feature,
dans le même ordre. Chaque `Plan du Scénario` devient un
`@pytest.mark.parametrize` dont les lignes sont celles du tableau
`Exemples:`, RECOPIÉES TELLES QUELLES (virgule décimale comprise) — comme le
demande REGLES-CALCUL-REMUNERATION.md §14.5. Chaque bloc cite sa ligne dans
le .feature : un écart entre les deux se retrouve en un coup d'œil.

Répartition (tableau du §14.5) :
    droit à rémunération  6 | assiette  5 | performance 20
    barème                8 | modulation 13 | montant     3   -> 55

Les valeurs attendues dépendent des PARAMÈTRES proposés par le sujet
(`parametrage_par_defaut`) : si le groupe en change un, ce sont ces
attendus qui bougent, pas les règles.

Non couverts ici, faute d'objet à tester dans une fonction pure :
- « Un seul chasseur est rémunéré pour une vente donnée » (.feature l. 52) ;
- la Règle `@tracabilite` (l. 275-300) : gel en base, notifications,
  recalcul des indicateurs. Elle relève de la persistance (§14.6).
============================================================================
"""

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal as D
from typing import Any

import pytest

from src.app.services.remuneration import (
    CENT,
    Exclusivite,
    LigneBareme,
    MotifRefus,
    OrigineVente,
    Vente,
    arrondi,
    calculer_honoraires,
    calculer_remuneration,
    calculer_score,
    droit_a_remuneration,
    majoration_anciennete,
    modulation_performance,
    noter_criteres,
    parametrage_par_defaut,
    parametres_honoraires_applicables,
    semaines_ecoulees,
    taux_de_tranche,
    taux_final,
)

PARAMS = parametrage_par_defaut()
BRUNO = 1
MANDAT = date(2025, 11, 14)
ACTE = date(2026, 7, 30)


def fr(nombre: str) -> D:
    """« 73,5 » du .feature -> Decimal('73.5')."""
    return D(nombre.replace(",", "."))


def pct(nombre: str) -> D:
    """« 9,4 » (en %) du .feature -> Decimal('0.094')."""
    return fr(nombre) / 100


def vente_bruno(**overrides: Any) -> Vente:
    """La vente de Bruno du §10 / §14.4 ; chaque test ne change que ce qu'il vise."""
    champs: dict[str, Any] = {
        "chasseur_id": BRUNO,
        "prix_acte": D(420000),
        "date_acte": ACTE,
        "date_signature_mandat": MANDAT,
        "date_fin_mandat": date(2026, 8, 14),
        "exclusivite": Exclusivite.EXCLUSIF,
        "origine": OrigineVente.CHASSEUR,
        "nb_visites": 5,
        "annees_anciennete": 3,
        "ventes_12_mois": 4,
        "mandats_12_mois": 9,
    }
    champs.update(overrides)
    return Vente(**champs)


# =============================================================================
# @droit-a-remuneration — 6 cas (.feature l. 29-50)
# =============================================================================

# Les libellés du .feature sont exactement les valeurs des Enum du module.
@pytest.mark.parametrize(
    ("exclusivite", "origine", "droit"),
    [
        ("exclusif", "le chasseur", "ouvert"),
        ("exclusif", "le client, en dehors du dispositif", "ouvert"),
        ("non-exclusif", "le chasseur", "ouvert"),
        ("non-exclusif", "le client, en dehors du dispositif", "fermé"),
        ("non-exclusif", "un chasseur d'une autre agence", "fermé"),
    ],
)
def test_droit_selon_exclusivite_et_origine(exclusivite: str, origine: str, droit: str):
    vente = vente_bruno(exclusivite=Exclusivite(exclusivite), origine=OrigineVente(origine))
    motif = droit_a_remuneration(vente)
    assert (motif is None) == (droit == "ouvert")


def test_acte_apres_echeance_du_mandat_ferme_le_droit():
    vente = vente_bruno(date_fin_mandat=date(2026, 5, 14), exclusivite=Exclusivite.NON_EXCLUSIF)
    resultat = calculer_remuneration(vente, PARAMS)
    assert resultat.droit_ouvert is False
    assert resultat.motif_refus is MotifRefus.MANDAT_EXPIRE
    assert resultat.montant == D("0.00")


# =============================================================================
# @assiette — 5 cas (.feature l. 68-79)
# =============================================================================

@pytest.mark.parametrize(
    ("prix", "honoraires"),
    [
        ("180000", "7500,00"),
        ("250000", "9250,00"),
        ("420000", "13500,00"),
        ("620000", "18500,00"),
        ("800000", "23000,00"),
    ],
)
def test_honoraires_sur_le_prix_acte(prix: str, honoraires: str):
    p = parametres_honoraires_applicables(PARAMS, ACTE)
    assert calculer_honoraires(fr(prix), p) == fr(honoraires)


# =============================================================================
# @performance — 20 cas (.feature l. 88-163)
# =============================================================================

@pytest.mark.parametrize(
    ("jours", "semaines", "note"),
    [(84, 12, 100), (90, 12, 100), (139, 19, 80), (258, 36, 40), (300, 42, 20), (400, 57, 0)],
)
def test_critere_delai(jours: int, semaines: int, note: int):
    acte = MANDAT + timedelta(days=jours)
    assert semaines_ecoulees(MANDAT, acte) == semaines
    vente = vente_bruno(date_acte=acte, date_fin_mandat=acte)
    assert noter_criteres(vente, PARAMS.performance)["delai"] == note


@pytest.mark.parametrize(
    ("visites", "note"),
    [(2, 100), (5, 80), (8, 60), (11, 40), (14, 20), (18, 0)],
)
def test_critere_visites(visites: int, note: int):
    assert noter_criteres(vente_bruno(nb_visites=visites), PARAMS.performance)["visites"] == note


@pytest.mark.parametrize(
    ("exclusivite", "note"),
    [("exclusif", 100), ("non-exclusif", 60)],
)
def test_critere_exclusivite(exclusivite: str, note: int):
    vente = vente_bruno(exclusivite=Exclusivite(exclusivite))
    assert noter_criteres(vente, PARAMS.performance)["exclusivite"] == note


@pytest.mark.parametrize(
    ("ventes", "mandats", "note_ventes", "note_mandats"),
    [(0, 3, 0, 30), (2, 6, 40, 60), (4, 9, 80, 90), (5, 10, 100, 100), (7, 14, 100, 100)],
)
def test_criteres_de_volume(ventes: int, mandats: int, note_ventes: int, note_mandats: int):
    notes = noter_criteres(vente_bruno(ventes_12_mois=ventes, mandats_12_mois=mandats), PARAMS.performance)
    assert (notes["ventes"], notes["mandats"]) == (note_ventes, note_mandats)


def test_score_global_agrege_les_cinq_criteres():
    notes = {"delai": D(40), "exclusivite": D(100), "ventes": D(80), "mandats": D(90), "visites": D(80)}
    assert calculer_score(notes, PARAMS.performance) == fr("73,5")


# =============================================================================
# @bareme — 8 cas (.feature l. 165-198)
# =============================================================================

@pytest.mark.parametrize(
    ("prix", "taux"),
    [("150000", "30"), ("199999", "30"), ("200000", "35"), ("420000", "40"), ("620000", "45"), ("800000", "50")],
)
def test_une_seule_tranche_un_seul_taux(prix: str, taux: str):
    assert taux_de_tranche(PARAMS, BRUNO, ACTE, fr(prix)) == pct(taux)


def test_bareme_en_vigueur_a_la_date_de_l_acte():
    debut = date(2026, 1, 1)
    bareme = (
        LigneBareme(debut, D(350000), pct("40"), D(499999), date_fin=date(2026, 6, 30)),
        LigneBareme(date(2026, 7, 1), D(350000), pct("38"), D(499999)),
    )
    params = replace(PARAMS, bareme=bareme)
    assert taux_de_tranche(params, BRUNO, ACTE, D(420000)) == pct("38")


def test_bareme_du_chasseur_prevaut_sur_le_defaut():
    nominatif = LigneBareme(date(2026, 1, 1), D(350000), pct("43"), D(499999), chasseur_id=BRUNO)
    params = replace(PARAMS, bareme=PARAMS.bareme + (nominatif,))
    assert taux_de_tranche(params, BRUNO, ACTE, D(420000)) == pct("43")


# =============================================================================
# @modulation — 13 cas (.feature l. 200-250)
# =============================================================================

@pytest.mark.parametrize(
    ("annees", "majoration"),
    [(0, "0"), (1, "2"), (3, "6"), (5, "10"), (8, "10")],
)
def test_majoration_anciennete(annees: int, majoration: str):
    assert majoration_anciennete(annees, PARAMS.modulation) == pct(majoration)


@pytest.mark.parametrize(
    ("score", "modulation"),
    [("0", "-20"), ("25", "-10"), ("50", "0"), ("73,5", "9,4"), ("100", "20")],
)
def test_modulation_performance(score: str, modulation: str):
    assert modulation_performance(fr(score), PARAMS.modulation) == pct(modulation)


@pytest.mark.parametrize(
    ("taux_base", "anciennete", "performance", "retenu"),
    [
        ("40", "6", "9,4", "46,16"),  # combinaison (l. 229)
        ("50", "10", "20", "60"),  # plafond : 65,00 % avant bornage (l. 236)
        ("22", "0", "-20", "20"),  # plancher : 17,60 % avant bornage (l. 244)
    ],
)
def test_taux_final(taux_base: str, anciennete: str, performance: str, retenu: str):
    r = taux_final(pct(taux_base), pct(anciennete), pct(performance), PARAMS.modulation)
    assert r == pct(retenu)


# =============================================================================
# @montant — 3 cas (.feature l. 252-272, et l. 81 pour l'assiette)
# =============================================================================

def test_calcul_de_bout_en_bout():
    r = calculer_remuneration(vente_bruno(), PARAMS)
    assert r.honoraires == fr("13500,00")
    assert r.score_performance == fr("73,5")
    assert r.taux_final == pct("46,16")
    assert r.montant == fr("6231,60")
    assert r.marge_entreprise == fr("7268,40")


def test_arrondi_au_centime_au_demi_superieur():
    brut = fr("9250,00") * pct("38,99")
    assert brut == fr("3606,575")
    assert arrondi(brut, CENT) == fr("3606,58")


def test_le_taux_s_applique_aux_honoraires_jamais_au_prix():
    r = calculer_remuneration(vente_bruno(), PARAMS)
    assert r.montant == arrondi(r.taux_final * fr("13500,00"), CENT)
    assert r.montant != arrondi(r.taux_final * fr("420000,00"), CENT)
