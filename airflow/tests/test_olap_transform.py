"""Tests de src/olap/transform.py (FLX6) — sans base, sans Airflow.

Les données sont construites à la main : chaque test change une seule chose
par rapport à `_data()` et regarde la mesure qu'elle doit faire bouger.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from src.olap.transform import build_star, chain_roots, day_row, delay_weeks


def _data(**over) -> dict[str, list[dict[str, object]]]:
    """Une vente (id 1) sur le mandat 10, chasseur 100, client 200, bien 300."""
    data: dict[str, list[dict[str, object]]] = {
        "sales": [{"id": 1, "signature_date": date(2026, 1, 29), "purchase_amount": 250_000,
                   "fees_amount": Decimal("7500.00"), "id_mandate": 10, "id_estate": 300,
                   "payment_amount": Decimal("1875.00")}],
        "mandates": [{"id": 10, "id_mandate_parent": None, "signature_date": date(2026, 1, 1),
                      "is_exclusive": True, "id_hunter": 100, "id_client": 200}],
        "visits": [],
        "hunters": [{"id": 100, "hire_date": date(2024, 3, 1), "is_hunter_ai": False,
                     "is_carte_t": True, "country_iso": "FR"}],
        "clients": [{"id": 200, "created_at": datetime(2025, 6, 2, 9, 0), "town": "Moulins",
                     "country_iso": "FR"}],
        "estates": [{"id": 300, "estate_type": "house", "typology": "T4", "surface": Decimal("95.50"),
                     "nb_rooms": 4, "energy_class": "C", "construction_date": date(1975, 1, 1),
                     "is_imported": False, "country_iso": "FR", "postal_code": "03000",
                     "town": "Moulins"}],
    }
    data.update(over)
    return data


def _fact(data=None) -> dict[str, object]:
    star = build_star(data or _data())
    assert len(star.facts) == 1, star.rejects
    return star.facts[0]


# --- délai en semaines ---

def test_delay_four_full_weeks():
    assert _fact()["delai_semaines"] == 4  # 2026-01-01 -> 2026-01-29 : 28 jours


def test_delay_rounds_down():
    assert delay_weeks(date(2026, 1, 1), date(2026, 1, 14)) == 1  # 13 jours


def test_delay_empty_without_signature():
    mandates = [{**_data()["mandates"][0], "signature_date": None}]
    assert _fact(_data(mandates=mandates))["delai_semaines"] is None


def test_delay_counts_from_root_of_chain():
    # Le mandat 11, signé le 2026-01-22, renouvelle le 10 (signé le 2026-01-01).
    child = {**_data()["mandates"][0], "id": 11, "id_mandate_parent": 10,
             "signature_date": date(2026, 1, 22)}
    sales = [{**_data()["sales"][0], "id_mandate": 11}]
    data = _data(mandates=_data()["mandates"] + [child], sales=sales)
    assert _fact(data)["delai_semaines"] == 4


def test_chain_roots_survive_a_loop():
    mandates: dict[int, dict[str, object]] = {1: {"id_mandate_parent": 2}, 2: {"id_mandate_parent": 1}}
    assert set(chain_roots(mandates)) == {1, 2}


# --- visites ---

def test_visits_of_chain_until_sale_day():
    child = {**_data()["mandates"][0], "id": 11, "id_mandate_parent": 10}
    visits = [{"id_mandate": 10, "visit_date": date(2026, 1, 5)},
              {"id_mandate": 11, "visit_date": date(2026, 1, 29)},  # le jour de l'acte : compte
              {"id_mandate": 11, "visit_date": date(2026, 2, 3)}]   # après l'acte : ne compte pas
    sales = [{**_data()["sales"][0], "id_mandate": 11}]
    data = _data(mandates=_data()["mandates"] + [child], visits=visits, sales=sales)
    assert _fact(data)["nb_visites_avant_achat"] == 2


# --- commission ---

def test_sale_without_payment_is_kept_with_empty_commission():
    sales = [{**_data()["sales"][0], "payment_amount": None}]
    star = build_star(_data(sales=sales))
    assert star.rejects == []
    assert star.facts[0]["commission_chasseur"] is None


# --- dimensions ---

def test_day_row_iso_calendar():
    assert day_row(date(2026, 1, 1)) == {"jour": date(2026, 1, 1), "annee": 2026, "trimestre": 1,
                                         "mois": 1, "semaine_iso": 1, "jour_semaine_iso": 4}


def test_dimensions_from_years():
    star = build_star(_data())
    assert star.dim_chasseur[0]["annee_embauche"] == 2024
    assert star.dim_client[0]["annee_inscription"] == 2025
    assert star.dim_bien[0]["annee_construction"] == 1975


def test_sector_deduplicated():
    second_estate = {**_data()["estates"][0], "id": 301}
    second_sale = {**_data()["sales"][0], "id": 2, "id_estate": 301}
    data = _data(estates=_data()["estates"] + [second_estate],
                 sales=_data()["sales"] + [second_sale])
    star = build_star(data)
    assert len(star.facts) == 2
    assert len(star.dim_bien) == 2
    assert len(star.dim_secteur) == 1
    assert len(star.dim_temps) == 1


def test_no_personal_data_in_star():
    star = build_star(_data())
    keys = {k for rows in (star.dim_chasseur, star.dim_client, star.dim_bien, star.facts)
            for r in rows for k in r}
    assert not keys & {"first_name", "last_name", "name", "email", "phone"}


# --- rejets et rapport ---

def test_unknown_mandate_rejected():
    sales = [{**_data()["sales"][0], "id_mandate": 99}]
    star = build_star(_data(sales=sales))
    assert star.facts == []
    assert star.report()["rejected_by_reason"] == {"unknown_mandate": 1}


def test_sale_before_mandate_rejected():
    sales = [{**_data()["sales"][0], "signature_date": date(2025, 12, 1)}]
    report = build_star(_data(sales=sales)).report()
    assert report["invalid_count"] == 1
    assert report["rejected_by_reason"] == {"sale_before_mandate_signature": 1}


def test_report_counts():
    bad = {**_data()["sales"][0], "id": 2, "id_estate": 999}
    report = build_star(_data(sales=_data()["sales"] + [bad])).report()
    assert report == {"read": 2, "loaded": 1, "invalid_count": 1, "pass_rate": 0.5,
                      "rejected_by_reason": {"unknown_estate": 1}}


def test_deterministic():
    assert build_star(_data()) == build_star(_data())
