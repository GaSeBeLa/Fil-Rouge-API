"""documents.py — Une ligne `estate` devient un document de l'index `estates`.

Chantier FLX, fiche FLX8. Sans base ni Elasticsearch : testé par
airflow/tests/test_search_documents.py.

Liste blanche : seuls les champs de FIELDS sortent de la base (ESTATE_QUERY
ne lit qu'eux) et entrent dans le document. Jamais la table estate_contact
(ADR-054), jamais id_author ; ni la rue ni le numéro : le point GPS suffit à
la carte (FLX11), et l'adresse exacte n'a rien à faire dans un index de
recherche.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text

from src.search.mapping import INDEX

# Colonnes de estate recopiées telles quelles (même nom dans le document).
FIELDS = (
    "id", "reference", "created_at", "country_iso", "postal_code", "town", "district",
    "estate_type", "typology", "floor", "energy_class", "price", "surface",
    "land_surface", "construction_date", "nb_rooms", "nb_bedrooms", "nb_bathrooms",
    "parking_spaces", "has_garden", "has_garage", "has_elevator", "has_cellar",
    "is_climatised", "needs_renovation", "information",
)

ESTATE_QUERY = text(
    f"SELECT {', '.join(FIELDS)}, latitude, longitude, id_author IS NULL AS is_imported "
    "FROM estate ORDER BY id"
)

ESTATE_IDS_QUERY = text("SELECT id FROM estate")


def _plain(value: object) -> object:
    """Valeur sérialisable en JSON : Decimal -> float, date -> ISO 8601."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def to_document(row: dict[str, object]) -> dict[str, object]:
    """Le document d'un bien ; champs vides omis."""
    doc = {name: _plain(row[name]) for name in FIELDS if row.get(name) is not None}
    doc["is_imported"] = bool(row["is_imported"])
    lat, lon = row.get("latitude"), row.get("longitude")
    if lat is not None and lon is not None:
        doc["location"] = {"lat": float(lat), "lon": float(lon)}  # pyright: ignore[reportArgumentType] -- NUMERIC(9,6)
    return doc


def index_actions(rows: Iterable[dict[str, object]]) -> Iterator[dict[str, object]]:
    """Actions pour helpers.bulk : _id = estate.id, rejouer remplace."""
    for row in rows:
        yield {"_index": INDEX, "_id": row["id"], "_source": to_document(row)}


def delete_actions(ids: Iterable[str]) -> Iterator[dict[str, object]]:
    """Actions pour helpers.bulk : retirer les biens absents de la base."""
    for _id in ids:
        yield {"_op_type": "delete", "_index": INDEX, "_id": _id}
