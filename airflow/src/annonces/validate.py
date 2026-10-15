"""validate.py — Dire si une annonce nettoyée entre dans `estate` v3.

Chantier FLX, fiche FLX3. Une validation rend `(True, "")` ou
`(False, "raison")`, comme dans le cours Airflow ; un rejet part en
quarantaine avec `_reject_reason`, `_reject_ts` et `_source_file`.

Chaque règle recopie une contrainte de la table `estate`, relevée par grep
dans `docker/init-v3/01_create_fil_rouge_immobilier.sql` (CREATE TABLE estate) :
  reference   VARCHAR(50) NOT NULL UNIQUE, CHECK (= btrim, <> '')
  estate_type VARCHAR(50) NOT NULL CHECK (IN 10 valeurs)
  price       INTEGER CHECK (price >= 0)
  energy_class CHAR(1) CHECK (IN 'A'..'G')
  latitude    NUMERIC(9,6) CHECK (BETWEEN -90 AND 90)
  longitude   NUMERIC(9,6) CHECK (BETWEEN -180 AND 180)
  chk_estate_coordinates_pair : les deux coordonnées, ou aucune
  floor       VARCHAR(10) CHECK (IN '0'..'9', '10 and more', 'last floor')
  nb_rooms    SMALLINT CHECK (> 0) ; nb_bedrooms, nb_balcony, nb_terrace,
              parking_spaces CHECK (>= 0)
  surface     NUMERIC(7,2) NOT NULL CHECK (surface > 0)
  town        VARCHAR(100) NOT NULL CHECK (= btrim, <> '')
  street      VARCHAR(100) ; street_number, postal_code VARCHAR(10)
  chk_estate_postal_code_format : FR -> '^[0-9]{5}$'
  information TEXT CHECK (char_length(information) <= 2000)
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from .clean import KEY

ESTATE_TYPES = {
    "Appartement", "Maison", "Studio", "Loft", "Villa",
    "Duplex", "Terrain", "Local commercial", "Chalet", "Château",
}
FLOORS = {str(n) for n in range(10)} | {"10 and more", "last floor"}
ENERGY_CLASSES = set("ABCDEFG")
FR_POSTAL_CODE = re.compile(r"^[0-9]{5}$")

# Longueurs maximales des colonnes VARCHAR.
MAX_LENGTHS = {KEY: 50, "town": 100, "street": 100, "street_number": 10, "postal_code": 10}
NON_NEGATIVE = ("nb_bedrooms", "nb_balcony", "nb_terrace", "parking_spaces")


def validate_annonce(row: dict[str, object]) -> tuple[bool, str]:
    """Rend (True, "") si la ligne respecte les contraintes de `estate`,
    sinon (False, raison de la première règle violée)."""
    if not row.get(KEY):
        return False, f"{KEY} manquante"
    estate_type = row.get("estate_type")
    if not estate_type:
        return False, "estate_type manquant"
    if estate_type not in ESTATE_TYPES:
        return False, "estate_type hors liste"
    surface = row.get("surface")
    if surface is None:
        return False, "surface manquante"
    if not isinstance(surface, (int, float)) or surface <= 0:
        return False, "surface nulle ou négative"
    if not row.get("town"):
        return False, "town manquante"

    for column, limit in MAX_LENGTHS.items():
        value = row.get(column)
        if value is not None and len(str(value)) > limit:
            return False, f"{column} trop longue"

    price = row.get("price")
    if price is not None and (not isinstance(price, int) or price < 0):
        return False, "price négatif"
    energy_class = row.get("energy_class")
    if energy_class is not None and energy_class not in ENERGY_CLASSES:
        return False, "energy_class hors liste"

    lat, lon = row.get("latitude"), row.get("longitude")
    if (lat is None) != (lon is None):
        return False, "coordonnées dépareillées"
    if isinstance(lat, (int, float)) and not -90 <= lat <= 90:
        return False, "latitude hors bornes"
    if isinstance(lon, (int, float)) and not -180 <= lon <= 180:
        return False, "longitude hors bornes"

    floor = row.get("floor")
    if floor is not None and floor not in FLOORS:
        return False, "floor hors liste"
    nb_rooms = row.get("nb_rooms")
    if isinstance(nb_rooms, int) and nb_rooms <= 0:
        return False, "nb_rooms nul ou négatif"
    for column in NON_NEGATIVE:
        value = row.get(column)
        if isinstance(value, int) and value < 0:
            return False, f"{column} négatif"

    postal_code = row.get("postal_code")
    if postal_code is not None and not FR_POSTAL_CODE.match(str(postal_code)):
        return False, "postal_code invalide"
    information = row.get("information")
    if information is not None and len(str(information)) > 2000:
        return False, "information trop longue"
    return True, ""


def split_valid(
    rows: list[dict[str, object]],
    source_file: str,
    now: datetime | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Sépare les lignes nettoyées en (valides, rejets).

    Un rejet garde sa ligne et porte `_reject_reason`, `_reject_ts` (ISO, UTC)
    et `_source_file`. Parmi les valides, une même clé gardée une fois :
    le dernier gagne. `now` fixe l'horodatage (tests, rejeu identique).
    """
    ts = (now or datetime.now(timezone.utc)).isoformat()
    valid_by_key: dict[object, dict[str, object]] = {}
    rejects: list[dict[str, object]] = []
    for row in rows:
        ok, reason = validate_annonce(row)
        if ok:
            # Réaffecter une clé déjà vue garde sa place et prend la dernière ligne.
            valid_by_key[row[KEY]] = row
        else:
            rejects.append({**row, "_reject_reason": reason, "_reject_ts": ts, "_source_file": source_file})
    return list(valid_by_key.values()), rejects
