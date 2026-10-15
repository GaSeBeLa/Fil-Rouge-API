"""
Tests des fonctions pures du faker de volume (seed_volume.py, fiche FLX13).

Sans base : le plan des ventes se vérifie avant qu'une ligne soit écrite.
Le script lui-même n'est appelé par aucun test (ADR-055) : il se lance à la
main sur la base de développement.
"""

import random
from datetime import date, timedelta

import pytest

from src.app.scripts.seed_volume import (
    MANDATE_LEAD_DAYS,
    NB_CLIENT_VISITS,
    NB_PROPOSED,
    SALES_FROM,
    SEED,
    add_months,
    plan_sales,
)

TODAY = date(2026, 10, 15)
ESTATES = list(range(1, 1001))


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 3, 2), date(2026, 9, 2)),  # l'exemple du seed de démo
        (date(2025, 8, 31), date(2026, 2, 28)),  # fin de mois, comme PostgreSQL
        (date(2023, 8, 31), date(2024, 2, 29)),  # année bissextile
        (date(2025, 9, 15), date(2026, 3, 15)),  # passage d'année
    ],
)
def test_add_months_matches_postgresql_interval(day, expected):
    assert add_months(day, 6) == expected


@pytest.fixture
def plans():
    return plan_sales(random.Random(SEED), 300, ESTATES, TODAY)


def test_each_estate_is_sold_once(plans):
    sold = [p.sold_estate_id for p in plans]
    assert len(plans) == 300
    assert len(set(sold)) == 300


def test_dates_follow_the_rules(plans):
    for p in plans:
        assert SALES_FROM <= p.sale_date < TODAY  # grilles en vigueur, rien dans le futur
        assert p.mandate_ends == add_months(p.mandate_signed, 6)
        assert p.mandate_signed < p.sale_date <= p.mandate_ends  # sinon 'mandate_expired'
        assert MANDATE_LEAD_DAYS[0] <= (p.sale_date - p.mandate_signed).days <= MANDATE_LEAD_DAYS[1]
        assert all(p.mandate_signed <= v <= p.sale_date for v in p.visit_dates)
        assert NB_CLIENT_VISITS[0] <= len(p.visit_dates) <= NB_CLIENT_VISITS[1]


def test_other_proposed_estates_never_repeat_the_sold_one(plans):
    for p in plans:
        assert p.sold_estate_id not in p.other_estate_ids
        assert len(p.other_estate_ids) <= NB_PROPOSED[1] - 1


def test_sales_are_numbered_in_date_order(plans):
    assert [p.number for p in plans] == list(range(1, 301))
    assert [p.sale_date for p in plans] == sorted(p.sale_date for p in plans)


def test_same_seed_same_plan():
    first = plan_sales(random.Random(SEED), 50, ESTATES, TODAY)
    again = plan_sales(random.Random(SEED), 50, ESTATES, TODAY)
    assert first == again


def test_more_sales_than_estates_is_refused():
    with pytest.raises(ValueError, match="ne se vend qu'une fois"):
        plan_sales(random.Random(SEED), 11, ESTATES[:10], TODAY)


def test_no_sale_before_the_grids():
    with pytest.raises(ValueError, match="grilles"):
        plan_sales(random.Random(SEED), 1, ESTATES, SALES_FROM)


def test_uses_both_kinds_of_mandate(plans):
    exclusive = sum(p.is_exclusive for p in plans)
    assert 0 < exclusive < len(plans)


def test_lead_time_reaches_back_before_the_grids(plans):
    # Les mandats remontent avant le 2026-01-01 : seules les ventes sont bornées.
    assert min(p.mandate_signed for p in plans) < SALES_FROM - timedelta(days=30)
