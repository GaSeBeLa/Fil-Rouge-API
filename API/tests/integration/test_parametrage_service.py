"""
test_parametrage_service.py — Le service qui lit les tables et rend un `Parametrage`.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Le test « la base égale le code » est dans test_seed_parametres.py. Ici, ce
qui est propre au service : choisir la bonne VERSION selon la date de l'acte.

Chaque test part du seed (05_parametres.sql, version du 2026-01-01), ajoute
une 2e version dans la transaction du test (annulée à la fin), puis interroge
le service à plusieurs dates.

Règles vérifiées :
- réglages du taux : la dernière version démarrée à la date demandée ;
- aucune version démarrée (table vide, date trop ancienne) : `BaremeIntrouvable`,
  une erreur de paramétrage, pas un cas métier ;
- honoraires : une version vaut jusqu'à la veille de la suivante (Q-SCH-17).
============================================================================
"""

from datetime import date
from decimal import Decimal as D

import pytest
from sqlmodel import Session

from src.app.models import HunterRateParameters, ParametersFees
from src.app.services.remuneration import BaremeIntrouvable, parametres_honoraires_applicables

from .test_seed_parametres import ACTE, apply_seed, service


def test_rate_version_in_force_at_the_date_is_the_one_read(db_session: Session):
    apply_seed(db_session)
    svc = service()
    first = svc.reglages_applicables(db_session, ACTE)
    # Une vraie nouvelle instance : `model_copy` contourne le suivi des attributs de SQLAlchemy.
    second = HunterRateParameters(**{**first.model_dump(exclude={"id", "created_at"}),
                                     "effective_from": date(2027, 1, 1),
                                     "rate_ceiling": D("0.65"), "window_months": 6})
    db_session.add(second)
    db_session.flush()

    before = svc.charger(db_session, date(2026, 12, 31))
    after = svc.charger(db_session, date(2027, 1, 1))
    assert before.modulation.taux_plafond == D("0.60")
    assert before.performance.fenetre_mois == 12
    assert after.modulation.taux_plafond == D("0.65")
    assert after.performance.fenetre_mois == 6
    # L'id rendu est celui à garder dans payment.id_hunter_rate_parameters.
    assert svc.reglages_applicables(db_session, date(2027, 1, 1)).id == second.id
    assert svc.reglages_applicables(db_session, date(2026, 12, 31)).id == first.id


def test_date_before_the_first_rate_version_is_a_parametrage_error(db_session: Session):
    apply_seed(db_session)
    with pytest.raises(BaremeIntrouvable):
        service().charger(db_session, date(2025, 12, 31))


def test_empty_tables_are_a_parametrage_error(db_session: Session):
    # Base de test sans seed : aucun réglage du taux.
    with pytest.raises(BaremeIntrouvable):
        service().charger(db_session, ACTE)


def test_a_fee_version_ends_the_day_before_the_next_one(db_session: Session):
    apply_seed(db_session)
    db_session.add(ParametersFees(effective_from=date(2027, 1, 1), fixed_amount=3500, rate=D("0.0300")))
    db_session.flush()

    parametrage = service().charger(db_session, date(2027, 2, 1))
    old, new = parametrage.honoraires
    assert old.date_fin == date(2026, 12, 31)
    assert new.date_fin is None
    # Le calcul choisit la version d'après la date de l'acte.
    assert parametres_honoraires_applicables(parametrage, date(2026, 12, 31)).montant_fixe == D(3000)
    assert parametres_honoraires_applicables(parametrage, date(2027, 1, 1)).montant_fixe == D(3500)
