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
    rejouer le même jour n'ajoute rien (UNIQUE (id_estate, seen_at)) ;
  - le contact du vendeur suit son bien dans estate_contact, dans la même
    transaction (FLX14) : un contact par bien (UNIQUE (id_estate)), « le
    dernier gagne » ; un contact saisi à la main (id_author renseigné) n'est
    jamais écrasé ; rien pour un bien saisi à la main ; un contact vide à la
    source n'efface pas celui qui existe.
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

CONTACT_COLUMNS = ["is_private", "agency_name", "contact_name", "phone_number", "email"]

UPSERT_CONTACT = text(
    f"INSERT INTO estate_contact (id_estate, {', '.join(CONTACT_COLUMNS)}) "
    f"VALUES (:id_estate, {', '.join(':' + c for c in CONTACT_COLUMNS)}) "
    "ON CONFLICT (id_estate) DO UPDATE SET "
    + ", ".join(f"{c} = excluded.{c}" for c in CONTACT_COLUMNS)
    + " WHERE estate_contact.id_author IS NULL"
    + " RETURNING id"
)

HAS_CONTACT = text("SELECT 1 FROM estate_contact WHERE id_estate = :id_estate")

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
    contacts_added: int = 0
    contacts_updated: int = 0
    contact_fields_dropped: int = 0


def _as_params(row: dict[str, object]) -> dict[str, object]:
    """Les seules colonnes de estate ; une date relue du JSON redevient une date."""
    params = {c: row.get(c) for c in ESTATE_COLUMNS}
    built = params.get("construction_date")
    if isinstance(built, str):
        params["construction_date"] = date.fromisoformat(built)
    return params


def _load_contact(conn, estate_id: int, contact: object) -> str | None:
    """Écrit le contact d'un bien importé ; rend 'added', 'updated', ou None
    quand rien n'est écrit (contact vide, ou saisi à la main et gardé)."""
    if not isinstance(contact, dict):
        return None
    existed = conn.execute(HAS_CONTACT, {"id_estate": estate_id}).first() is not None
    params = {"id_estate": estate_id, **{c: contact.get(c) for c in CONTACT_COLUMNS}}
    if conn.execute(UPSERT_CONTACT, params).scalar_one_or_none() is None:
        return None  # contact saisi à la main : la clause WHERE l'a laissé tel quel
    return "updated" if existed else "added"


def load_estates(conn, rows: list[dict[str, object]], seen_at: date) -> LoadReport:
    """Insère ou met à jour chaque bien, note son prix du jour et range son
    contact ; rend les comptes. Une liste vide rend un rapport à zéro."""
    keys = [row[KEY] for row in rows]
    existing = {r[0] for r in conn.execute(EXISTING_KEYS, {"keys": keys})} if keys else set()

    inserted = updated = skipped_manual = prices_added = 0
    contacts = {"added": 0, "updated": 0}
    fields_dropped = sum(int(str(row.get("_contact_fields_dropped") or 0)) for row in rows)
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
        outcome = _load_contact(conn, estate_id, row.get("contact"))
        if outcome is not None:
            contacts[outcome] += 1
    return LoadReport(inserted, updated, skipped_manual, prices_added,
                      contacts["added"], contacts["updated"], fields_dropped)
