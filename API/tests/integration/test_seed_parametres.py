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

La relecture passe par `ParametrageService`, le vrai service : ce test prouve
donc aussi que le service sait lire ce que le seed écrit.

Ce qui est vérifié :
- le seed remplit les trois tables (1 / 5 / 1 lignes) ;
- il est rejouable (une 2e passe n'ajoute rien) ;
- le `Parametrage` lu en base est ÉGAL à `parametrage_par_defaut()` ;
- ce `Parametrage` donne l'exemple de Bruno du sujet (§10) : 6 231,60 €.
============================================================================
"""

from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest
from sqlmodel import Session

from src.app.repositories.commission_scale_repository import CommissionScaleRepository
from src.app.repositories.hunter_rate_parameters_repository import HunterRateParametersRepository
from src.app.repositories.parameters_fees_repository import ParametersFeesRepository
from src.app.services.parametrage_service import ParametrageService
from src.app.services.remuneration import (
    Exclusivite,
    OrigineVente,
    Vente,
    calculer_remuneration,
    parametrage_par_defaut,
)

SEED = Path(__file__).resolve().parents[3] / "docker" / "init-v3" / "05_parametres.sql"
ACTE = date(2026, 7, 30)


def apply_seed(db_session: Session) -> None:
    """Rejoue le fichier du seed dans la transaction du test.

    Passe par le curseur du pilote, sans paramètres : le fichier contient des `%`
    (dans ses commentaires) qu'une exécution paramétrée tenterait d'interpréter.
    """
    if not SEED.exists():
        # Le conteneur `api` ne monte que src/ et tests/ (docker-compose.yml) : il ne voit pas docker/.
        pytest.skip(f"Seed introuvable ({SEED}) : lancer ces tests depuis API/, sur la machine, pas dans le conteneur.")
    cursor = db_session.connection().connection.cursor()
    cursor.execute(SEED.read_text(encoding="utf-8"))


def count(db_session: Session, table: str) -> int:
    # `table` vient de ce fichier, jamais d'une entrée extérieure.
    return db_session.connection().exec_driver_sql(f"SELECT count(*) FROM {table}").scalar_one()


def service() -> ParametrageService:
    return ParametrageService(ParametersFeesRepository(), CommissionScaleRepository(), HunterRateParametersRepository())


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
    assert service().charger(db_session, ACTE) == parametrage_par_defaut()


def test_seed_gives_the_worked_example_of_the_subject(db_session: Session):
    # Bruno, §10 de REGLES-CALCUL-REMUNERATION.md : 420 000 € -> 6 231,60 €.
    apply_seed(db_session)
    bruno = Vente(
        chasseur_id=1,
        prix_acte=D(420000),
        date_acte=ACTE,
        date_signature_mandat=date(2025, 11, 14),
        date_fin_mandat=date(2026, 8, 14),
        exclusivite=Exclusivite.EXCLUSIF,
        origine=OrigineVente.CHASSEUR,
        nb_visites=5,
        annees_anciennete=3,
        ventes_12_mois=4,
        mandats_12_mois=9,
    )
    result = calculer_remuneration(bruno, service().charger(db_session, ACTE))
    assert result.honoraires == D("13500.00")
    assert result.taux_final == D("0.4616")
    assert result.montant == D("6231.60")
