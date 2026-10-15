"""load.py — Charger les annonces valides dans `estate`, sans doublon.

Chantier FLX, fiche FLX4. Reçoit une connexion SQLAlchemy ouverte (le DAG la
tire de la connexion Airflow fil_rouge_db) : la transaction appartient à
l'appelant. Le SQL n'utilise que ce que PostgreSQL et SQLite comprennent tous
deux (ON CONFLICT ... DO UPDATE, excluded), ce qui laisse tester sans Docker.

Règles :
  - la clé d'une annonce est estate.reference (question flux-16, tranchée A
    par Seb le 2026-10-15) : une référence déjà connue met le bien à jour,
    « le dernier gagne » ;
  - un bien saisi à la main (id_author renseigné, ADR-047) n'est jamais
    écrasé par l'import ; un bien importé garde id_author vide ;
  - une ligne estate_price_history par bien et par jour vu (flux-12b) :
    rejouer le même jour n'ajoute rien (UNIQUE (id_estate, seen_at)).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import bindparam, text

from .clean import ESTATE_COLUMNS, KEY

_UPDATED_COLUMNS = [c for c in ESTATE_COLUMNS if c != KEY]

UPSERT_ESTATE = text(
    f"INSERT INTO estate ({', '.join(ESTATE_COLUMNS)}) "
    f"VALUES ({', '.join(':' + c for c in ESTATE_COLUMNS)}) "
    f"ON CONFLICT ({KEY}) DO UPDATE SET "
    + ", ".join(f"{c} = excluded.{c}" for c in _UPDATED_COLUMNS)
    + " WHERE estate.id_author IS NULL"
    + " RETURNING id"
)

INSERT_PRICE = text(
    "INSERT INTO estate_price_history (id_estate, price, seen_at) "
    "VALUES (:id_estate, :price, :seen_at) "
    "ON CONFLICT (id_estate, seen_at) DO NOTHING"
)

EXISTING_KEYS = text(f"SELECT {KEY} FROM estate WHERE {KEY} IN :keys").bindparams(
    bindparam("keys", expanding=True)
)


@dataclass(frozen=True)
class LoadReport:
    """Ce que le chargement a fait, pour les logs du DAG."""

    inserted: int
    updated: int
    skipped_manual: int
    prices_added: int


def _as_params(row: dict[str, object]) -> dict[str, object]:
    """Les seules colonnes de estate ; une date relue du JSON redevient une date."""
    params = {c: row.get(c) for c in ESTATE_COLUMNS}
    built = params.get("construction_date")
    if isinstance(built, str):
        params["construction_date"] = date.fromisoformat(built)
    return params


def load_estates(conn, rows: list[dict[str, object]], seen_at: date) -> LoadReport:
    """Insère ou met à jour chaque bien, puis note son prix du jour."""
    keys = [row[KEY] for row in rows]
    existing = {r[0] for r in conn.execute(EXISTING_KEYS, {"keys": keys})} if keys else set()

    inserted = updated = skipped_manual = prices_added = 0
    for row in rows:
        estate_id = conn.execute(UPSERT_ESTATE, _as_params(row)).scalar_one_or_none()
        if estate_id is None:
            # Conflit sur un bien saisi à la main : la clause WHERE l'a laissé tel quel.
            skipped_manual += 1
            continue
        if row[KEY] in existing:
            updated += 1
        else:
            inserted += 1
        price = row.get("price")
        if price is not None:
            result = conn.execute(INSERT_PRICE, {"id_estate": estate_id, "price": price, "seen_at": seen_at})
            prices_added += result.rowcount
    return LoadReport(inserted, updated, skipped_manual, prices_added)
