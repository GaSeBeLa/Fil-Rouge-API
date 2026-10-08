"""
test_seed_parametres.py — Le seed `docker/init-v3/05_parametres.sql` dit la même chose que le code.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Le seed met trois tables de paramètres en base : parameters_fees,
commission_scale, hunter_rate_parameters. Le calcul de rémunération, lui, a
ses valeurs par défaut dans le code (`parametrage_par_defaut`). Deux
endroits disent la même chose : ces tests vérifient qu'ils ne divergent pas.

Chaque test rejoue le FICHIER du seed dans la transaction du test (annulée à
la fin, voir conftest.py) : c'est bien le script livré qui est testé, pas une
copie. La base de test ne contient pas le seed : create_test_db.sh ne rejoue
que 01, 02 et 04.

Ce qui est vérifié :
- le seed remplit les trois tables (1 / 5 / 1 lignes) ;
- il est rejouable (une 2e passe n'ajoute rien) ;
- les lignes relues en base, remises dans un `Parametrage`, sont ÉGALES à
  `parametrage_par_defaut()` ;
- ce `Parametrage` donne l'exemple de Bruno du sujet (§10) : 6 231,60 €.
============================================================================
"""

from datetime import date
from decimal import Decimal as D
from pathlib import Path

from sqlmodel import Session

from src.app.services.remuneration import (
    Exclusivite,
    LigneBareme,
    OrigineVente,
    Palier,
    Parametrage,
    ParametresHonoraires,
    ParametresModulation,
    ParametresPerformance,
    Vente,
    calculer_remuneration,
    parametrage_par_defaut,
)

SEED = Path(__file__).resolve().parents[3] / "docker" / "init-v3" / "05_parametres.sql"


def apply_seed(db_session: Session) -> None:
    """Rejoue le fichier du seed dans la transaction du test.

    Passe par le curseur du pilote, sans paramètres : le fichier contient des `%`
    (dans ses commentaires) qu'une exécution paramétrée tenterait d'interpréter.
    """
    cursor = db_session.connection().connection.cursor()
    cursor.execute(SEED.read_text(encoding="utf-8"))


def count(db_session: Session, table: str) -> int:
    # `table` vient de ce fichier, jamais d'une entrée extérieure.
    return db_session.connection().exec_driver_sql(f"SELECT count(*) FROM {table}").scalar_one()


def tiers(raw: list[dict]) -> tuple[Palier, ...]:
    return tuple(Palier(None if t["maximum"] is None else D(t["maximum"]), D(t["note"])) for t in raw)


def parametrage_depuis_la_base(db_session: Session) -> Parametrage:
    """Le `Parametrage` que construirait un service lisant les trois tables."""
    connection = db_session.connection()
    fees = connection.exec_driver_sql(
        "SELECT effective_from, fixed_amount, rate FROM parameters_fees ORDER BY effective_from"
    ).all()
    scale = connection.exec_driver_sql(
        "SELECT valid_from, amount_min, rate, amount_max, valid_until, id_hunter"
        " FROM commission_scale ORDER BY amount_min"
    ).all()
    (rate,) = connection.exec_driver_sql(
        "SELECT weight_delay, weight_exclusivity, weight_sales, weight_mandates, weight_visits,"
        " delay_tiers, visit_tiers, score_exclusive, score_non_exclusive,"
        " points_per_sale, points_per_mandate, window_months,"
        " seniority_rate_per_year, seniority_cap, score_pivot, score_half_range,"
        " performance_amplitude, rate_floor, rate_ceiling"
        " FROM hunter_rate_parameters ORDER BY effective_from DESC LIMIT 1"
    ).all()
    return Parametrage(
        honoraires=tuple(ParametresHonoraires(f[0], D(f[1]), f[2]) for f in fees),
        bareme=tuple(
            LigneBareme(s[0], D(s[1]), s[2], None if s[3] is None else D(s[3]), s[4], s[5]) for s in scale
        ),
        performance=ParametresPerformance(
            poids_delai=rate[0],
            poids_exclusivite=rate[1],
            poids_ventes=rate[2],
            poids_mandats=rate[3],
            poids_visites=rate[4],
            paliers_delai=tiers(rate[5]),
            paliers_visites=tiers(rate[6]),
            note_exclusif=rate[7],
            note_non_exclusif=rate[8],
            points_par_vente=rate[9],
            points_par_mandat=rate[10],
            fenetre_mois=rate[11],
        ),
        modulation=ParametresModulation(
            taux_par_annee=rate[12],
            plafond_anciennete=rate[13],
            score_pivot=rate[14],
            demi_amplitude_score=rate[15],
            amplitude_performance=rate[16],
            taux_plancher=rate[17],
            taux_plafond=rate[18],
        ),
    )


def test_seed_fills_the_three_parameter_tables(db_session: Session):
    # Base de test : les trois tables partent vides (02_migration.sql:39-42).
    assert (count(db_session, "parameters_fees"), count(db_session, "commission_scale"),
            count(db_session, "hunter_rate_parameters")) == (0, 0, 0)
    apply_seed(db_session)
    assert count(db_session, "parameters_fees") == 1
    assert count(db_session, "commission_scale") == 5
    assert count(db_session, "hunter_rate_parameters") == 1


def test_seed_can_be_replayed(db_session: Session):
    apply_seed(db_session)
    apply_seed(db_session)
    assert count(db_session, "parameters_fees") == 1
    assert count(db_session, "commission_scale") == 5
    assert count(db_session, "hunter_rate_parameters") == 1


def test_seed_equals_the_default_parametrage_of_the_code(db_session: Session):
    # Deux endroits disent la même chose (le code et la base) : ils ne divergent pas.
    apply_seed(db_session)
    assert parametrage_depuis_la_base(db_session) == parametrage_par_defaut()


def test_seed_gives_the_worked_example_of_the_subject(db_session: Session):
    # Bruno, §10 de REGLES-CALCUL-REMUNERATION.md : 420 000 € -> 6 231,60 €.
    apply_seed(db_session)
    bruno = Vente(
        chasseur_id=1,
        prix_acte=D(420000),
        date_acte=date(2026, 7, 30),
        date_signature_mandat=date(2025, 11, 14),
        date_fin_mandat=date(2026, 8, 14),
        exclusivite=Exclusivite.EXCLUSIF,
        origine=OrigineVente.CHASSEUR,
        nb_visites=5,
        annees_anciennete=3,
        ventes_12_mois=4,
        mandats_12_mois=9,
    )
    result = calculer_remuneration(bruno, parametrage_depuis_la_base(db_session))
    assert result.honoraires == D("13500.00")
    assert result.taux_final == D("0.4616")
    assert result.montant == D("6231.60")
