"""Tests de airflow/src/annonces/validate.py : un test par règle de rejet."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.annonces.clean import KEY, clean_annonce
from src.annonces.validate import split_valid, validate_annonce

NOW = datetime(2026, 10, 15, 2, 0, tzinfo=timezone.utc)


def _row(**changes: object) -> dict[str, object]:
    """Une annonce nettoyée valide, puis les changements demandés."""
    row = clean_annonce({"reference": "AN-TEST0001", "type_bien": "Maison", "ville": "Toulouse",
                         "code_postal": "31000", "surface": "100", "prix": "250000"})
    row.update(changes)
    return row


def test_valid_row_passes():
    assert validate_annonce(_row()) == (True, "")


@pytest.mark.parametrize(("changes", "reason"), [
    ({KEY: None}, f"{KEY} manquante"),
    ({"estate_type": None}, "estate_type manquant"),
    ({"estate_type": "Péniche"}, "estate_type hors liste"),
    ({"surface": None}, "surface manquante"),
    ({"surface": 0.0}, "surface nulle ou négative"),
    ({"town": None}, "town manquante"),
    ({KEY: "X" * 51}, f"{KEY} trop longue"),
    ({"town": "T" * 101}, "town trop longue"),
    ({"street": "S" * 101}, "street trop longue"),
    ({"street_number": "1" * 11}, "street_number trop longue"),
    ({"postal_code": "1" * 11}, "postal_code trop longue"),
    ({"price": -1}, "price négatif"),
    ({"energy_class": "H"}, "energy_class hors liste"),
    ({"latitude": 43.6, "longitude": None}, "coordonnées dépareillées"),
    ({"latitude": 91.0, "longitude": 1.0}, "latitude hors bornes"),
    ({"latitude": 43.6, "longitude": 181.0}, "longitude hors bornes"),
    ({"floor": "-1"}, "floor hors liste"),
    ({"nb_rooms": 0}, "nb_rooms nul ou négatif"),
    ({"nb_bedrooms": -1}, "nb_bedrooms négatif"),
    ({"nb_balcony": -1}, "nb_balcony négatif"),
    ({"nb_terrace": -1}, "nb_terrace négatif"),
    ({"parking_spaces": -1}, "parking_spaces négatif"),
    ({"postal_code": "3100"}, "postal_code invalide"),
    ({"information": "x" * 2001}, "information trop longue"),
])
def test_each_rule_rejects_with_its_reason(changes, reason):
    assert validate_annonce(_row(**changes)) == (False, reason)


def test_reject_carries_reason_timestamp_and_source_file():
    valid, rejects = split_valid([_row(), _row(**{KEY: "AN-TEST0002", "surface": None})], "annonces.csv", NOW)

    assert len(valid) == 1
    assert len(rejects) == 1
    assert rejects[0]["_reject_reason"] == "surface manquante"
    assert rejects[0]["_reject_ts"] == "2026-10-15T02:00:00+00:00"
    assert rejects[0]["_source_file"] == "annonces.csv"


def test_same_key_last_one_wins():
    first, last = _row(price=100000), _row(price=120000)

    valid, rejects = split_valid([first, last], "annonces.csv", NOW)

    assert [r["price"] for r in valid] == [120000]
    assert rejects == []


def test_two_passes_give_the_same_output():
    rows = [_row(), _row(**{KEY: "AN-TEST0002", "town": None}), _row(price=1)]

    assert split_valid(rows, "annonces.csv", NOW) == split_valid(rows, "annonces.csv", NOW)
