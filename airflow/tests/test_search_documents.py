"""Tests de src/search/documents.py et mapping.py (FLX8) — sans base ni Elasticsearch."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from src.search.documents import FIELDS, delete_actions, index_actions, to_document
from src.search.mapping import INDEX, MAPPINGS

CONTACT_FIELDS = {"first_name", "last_name", "name", "email", "phone", "phone_number",
                  "street", "street_number", "id_author", "contact"}


def _row(**over) -> dict[str, object]:
    row: dict[str, object] = {name: None for name in FIELDS}
    row.update({
        "id": 7, "reference": "ANN-7", "created_at": datetime(2026, 10, 15, 2, 0),
        "country_iso": "FR", "postal_code": "03000", "town": "Moulins",
        "estate_type": "Maison", "price": 180_000, "surface": Decimal("95.50"),
        "construction_date": date(1975, 1, 1), "needs_renovation": False,
        "information": "Belle maison bourbonnaise avec puits",
        "latitude": Decimal("46.566000"), "longitude": Decimal("3.333000"),
        "is_imported": True,
    })
    row.update(over)
    return row


def test_whitelist_matches_mapping():
    # Le document ne porte que des champs du mapping : "dynamic": "strict"
    # refuserait les autres, et la liste blanche se garde ici.
    doc = to_document(_row())
    assert set(doc) <= set(MAPPINGS["properties"])


def test_no_contact_field():
    keys = set(to_document(_row(street="rue du Puits", street_number="3"))) | set(MAPPINGS["properties"])
    assert not keys & CONTACT_FIELDS


def test_location_from_both_coordinates():
    assert to_document(_row())["location"] == {"lat": 46.566, "lon": 3.333}


def test_no_location_without_coordinates():
    assert "location" not in to_document(_row(latitude=None, longitude=None))


def test_json_friendly_values():
    doc = to_document(_row())
    assert doc["surface"] == 95.5
    assert doc["construction_date"] == "1975-01-01"
    assert doc["created_at"] == "2026-10-15T02:00:00"


def test_empty_fields_left_out():
    doc = to_document(_row())
    assert "typology" not in doc
    assert doc["needs_renovation"] is False  # un faux n'est pas un vide


def test_index_action_id_is_estate_id():
    (action,) = list(index_actions([_row()]))
    assert action["_index"] == INDEX
    assert action["_id"] == 7


def test_delete_actions():
    assert list(delete_actions(["3"])) == [{"_op_type": "delete", "_index": INDEX, "_id": "3"}]


def test_mapping_is_strict_and_french():
    assert MAPPINGS["dynamic"] == "strict"
    assert MAPPINGS["properties"]["information"]["analyzer"] == "french"
    assert MAPPINGS["properties"]["location"]["type"] == "geo_point"
