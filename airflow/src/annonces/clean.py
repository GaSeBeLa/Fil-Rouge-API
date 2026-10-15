"""clean.py — Nettoyer une annonce brute en une ligne prête pour `estate` v3.

Chantier FLX, fiche FLX3. Fonctions pures : aucune lecture de fichier, aucune
base, aucun Airflow (le DAG orchestre, `src/` transforme).

Les règles sont RECOPIÉES de `normalised/normalised.py` (dépôt Fil-Rouge),
qui visait l'ancien schéma `docker/init/01`. Ce qui change pour le schéma v3
(`docker/init-v3/01_create_fil_rouge_immobilier.sql`) est dit sur place :
  - price en euros entiers (v3 : `price INTEGER`), plus de conversion en K€ ;
  - floor en texte de la liste du CHECK ('0'..'9', '10 and more', 'last floor') ;
  - energy_class reprend la lettre du DPE (Q-MIG-06, comme init-v3/03) ;
  - country_iso vaut 'FR' (comme init-v3/03 : toutes les annonces sont
    françaises), sinon le CHECK du code postal refuse la ligne (Q-SCH-11).

Jamais de contact du vendeur dans la ligne : les colonnes contact.* de la
source ne sont pas lues (ADR-054).
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timezone

# Clé de l'annonce, qui sert au dédoublonnage et à l'import sans doublon.
# La colonne « reference » de la source y est recopiée.
KEY = "reference"

# Colonnes de `estate` remplies par l'import, dans l'ordre de init-v3/03
# (id, created_at, typology, district, id_author et les colonnes d'énergie
# sans source restent à leur défaut).
ESTATE_COLUMNS = [
    KEY, "country_iso", "energy_class", "estate_type", "price", "construction_date",
    "latitude", "longitude", "floor", "nb_rooms", "nb_bedrooms", "nb_bathrooms",
    "nb_toilets", "nb_swimming_pool", "has_garden", "nb_balcony", "nb_terrace",
    "is_climatised", "surface", "land_surface", "has_cellar", "has_view", "is_quiet",
    "is_bright", "has_garage", "has_elevator", "has_chimney", "parking_spaces",
    "has_separate_kitchen", "needs_renovation", "town", "street", "street_number",
    "postal_code", "information",
]

FRENCH_MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}


def clean_str(v: object) -> str | None:
    """Chaîne nettoyée (strip) ou None si vide."""
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def parse_bool_presence(v: object) -> bool:
    """Colonnes « présence » (jardin, cave, ascenseur, calme, lumineux,
    terrasse, balcon) : 'True' ou vide dans la source, jamais 'False' ;
    vide veut dire absent, donc False (normalised.py)."""
    s = clean_str(v)
    return s is not None and s.lower() == "true"


def bool_to_count(v: object) -> int:
    """Présence -> compteur 0/1 (nb_balcony, nb_terrace)."""
    return 1 if parse_bool_presence(v) else 0


def parse_float(v: object) -> float | None:
    s = clean_str(v)
    if s is None:
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def parse_int(v: object) -> int | None:
    f = parse_float(v)
    return int(f) if f is not None else None


def parse_price_eur(v: object) -> int | None:
    """'406042 €' ou '406042' -> 406042, en euros entiers (CLAUDE.md, règle 4)."""
    s = clean_str(v)
    if s is None:
        return None
    cleaned = s.replace("€", "").replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        return int(round(float(cleaned)))
    except ValueError:
        return None


def parse_surface(surface: object, surface_m2: object) -> float | None:
    """Fusionne les deux colonnes redondantes 'surface' / 'surface_m2'."""
    value = parse_float(surface)
    return value if value is not None else parse_float(surface_m2)


def parse_floor(v: object) -> str | None:
    """'RDC' -> '0' ; 0 à 9 -> lui-même ; 10 et plus -> '10 and more' ;
    'dernier étage' -> 'last floor' ; illisible -> None (normalised.py,
    parse_etage, rendu en texte pour le CHECK v3)."""
    s = clean_str(v)
    if s is None:
        return None
    if s.upper() == "RDC":
        return "0"
    try:
        n = int(s)
    except ValueError:
        return "last floor" if "dernier" in s.lower() else None
    # Un étage négatif sort tel quel : la validation le refusera (CHECK floor).
    return str(n) if n < 10 else "10 and more"


def split_address(v: object) -> tuple[str | None, str | None]:
    """'200 avenue des Champs' -> ('200', 'avenue des Champs')."""
    s = clean_str(v)
    if s is None:
        return None, None
    parts = s.split(" ", 1)
    if len(parts) == 2 and parts[0].isdigit():
        return parts[0], clean_str(parts[1])
    return None, s


def parse_date(v: object) -> date | None:
    """Tous les formats de date_publication de la source vers une date :
    timestamp UNIX, ISO avec heure, ISO, '25 octobre 2024', JJ/MM/AAAA,
    MM-JJ-AAAA (normalised.py, parse_date_publication)."""
    s = clean_str(v)
    if s is None:
        return None
    try:
        if s.isdigit():
            return datetime.fromtimestamp(int(s), tz=timezone.utc).date()
        if "T" in s:
            return datetime.fromisoformat(s).date()
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            return date.fromisoformat(s)
        if "/" in s:
            day, month, year = s.split("/")
            return date(int(year), int(month), int(day))
        if len(s) == 10 and s[2] == "-" and s[5] == "-":
            month, day, year = s.split("-")
            return date(int(year), int(month), int(day))
        parts = s.lower().split(" ")
        if len(parts) == 3 and parts[1] in FRENCH_MONTHS:
            day, month_name, year = parts
            return date(int(year), FRENCH_MONTHS[month_name], int(day))
    except (ValueError, IndexError, OverflowError):
        return None
    return None


def derive_needs_renovation(description: str | None) -> bool:
    return description is not None and "travaux" in description.lower()


def derive_has_view(title: str | None, description: str | None) -> bool:
    return "vue dégagée" in f"{title or ''} {description or ''}".lower()


def derive_parking_spaces(description: str | None) -> int:
    """Pas de colonne parking dans la source : 1 si le texte le mentionne."""
    return 1 if description is not None and "parking" in description.lower() else 0


def clean_annonce(row: Mapping[str, object]) -> dict[str, object]:
    """Une ligne brute de annonces.csv -> une ligne aux colonnes de `estate` v3.

    Rend aussi `_published_on` (date de publication lue, hors `estate`).
    Relancer sur la même ligne rend la même sortie.
    """
    street_number, street = split_address(row.get("adresse"))
    description = clean_str(row.get("description"))
    title = clean_str(row.get("titre"))
    year = parse_int(row.get("annee_construction"))
    dpe = clean_str(row.get("dpe"))

    return {
        KEY: clean_str(row.get("reference")),
        "country_iso": "FR",
        "energy_class": dpe.upper() if dpe else None,
        "estate_type": clean_str(row.get("type_bien")),
        "price": parse_price_eur(row.get("prix")),
        "construction_date": date(year, 1, 1) if year and 1 <= year <= 9999 else None,
        "latitude": parse_float(row.get("latitude")),
        "longitude": parse_float(row.get("longitude")),
        "floor": parse_floor(row.get("etage")),
        "nb_rooms": parse_int(row.get("nb_pieces")),
        "nb_bedrooms": parse_int(row.get("nb_chambres")),
        "nb_bathrooms": None,       # aucune source (normalised.py)
        "nb_toilets": None,
        "nb_swimming_pool": None,
        "has_garden": parse_bool_presence(row.get("jardin")),
        "nb_balcony": bool_to_count(row.get("balcon")),
        "nb_terrace": bool_to_count(row.get("terrasse")),
        "is_climatised": False,     # 0 mention sur toute la source (normalised.py)
        "surface": parse_surface(row.get("surface"), row.get("surface_m2")),
        "land_surface": None,
        "has_cellar": parse_bool_presence(row.get("cave")),
        "has_view": derive_has_view(title, description),
        "is_quiet": parse_bool_presence(row.get("calme")),
        "is_bright": parse_bool_presence(row.get("lumineux")),
        "has_garage": False,        # idem is_climatised
        "has_elevator": parse_bool_presence(row.get("ascenseur")),
        "has_chimney": False,
        "parking_spaces": derive_parking_spaces(description),
        "has_separate_kitchen": False,
        "needs_renovation": derive_needs_renovation(description),
        "town": clean_str(row.get("ville")),
        "street": street,
        "street_number": street_number,
        "postal_code": clean_str(row.get("code_postal")),
        "information": description,
        "_published_on": parse_date(row.get("date_publication")),
    }
