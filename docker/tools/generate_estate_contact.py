"""
generate_estate_contact.py — Écrit docker/init-v3/06_populate_estate_contact.sql
depuis annonces_normalised.csv (dépôt Fil-Rouge, dossier normalised/).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Le CSV nettoyé par normalised.py garde, pour chaque annonce, cinq colonnes
de contact que 03_populate_estate.sql n'importait pas (ADR-054) :
contact_name, contact_phone, contact_email, contact_agency, is_particulier.
Ce script en fait une ligne de estate_contact par bien, rattachée par la
référence de l'annonce, comme les photos de 03.

Règles (ADR-054) :
- pas de ligne si les quatre champs de contact sont vides ;
- téléphone national 0XXXXXXXXX → +33XXXXXXXXX (format de ADR-007) ;
- seller_type : 'private' si l'annonce dit « particulier » sans agence,
  'agency' si elle a une agence sans dire « particulier », sinon vide :
  normalised.py change un « particulier » vide en False, et 166 annonces
  disent « particulier » avec une agence ; on ne devine pas.

Lancement, depuis la racine de Fil-Rouge-API :

    python docker/tools/generate_estate_contact.py <chemin>/annonces_normalised.csv

Le script compte ce qu'il écrit et l'affiche ; il échoue si une valeur
sortirait du format de la table, au lieu d'écrire un SQL que la base refuserait.
============================================================================
"""

import csv
import re
import sys
from collections import Counter
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent.parent / "init-v3" / "06_populate_estate_contact.sql"

# Mêmes formes que les CHECK de estate_contact (01_create_fil_rouge_immobilier.sql).
PHONE_RE = re.compile(r"^\+[1-9]([ -]?[0-9]){1,14}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
NATIONAL_PHONE_RE = re.compile(r"^0[0-9]{9}$")
MAX_TEXT = 100


def clean(value: str | None) -> str | None:
    """Vide, « NULL » ou blanc → None ; sinon la valeur sans blancs autour."""
    if value is None:
        return None
    value = value.strip()
    return None if value in ("", "NULL") else value


def to_international(phone: str) -> str:
    """0612345678 → +33612345678 (ADR-007). Tout autre format est refusé."""
    if not NATIONAL_PHONE_RE.match(phone):
        raise ValueError(f"téléphone hors format national : {phone!r}")
    return "+33" + phone[1:]


def seller_type(is_private: bool, agency: str | None) -> str | None:
    if is_private and agency is None:
        return "private"
    if agency is not None and not is_private:
        return "agency"
    return None


def sql_literal(value: str | None) -> str:
    return "NULL" if value is None else "'" + value.replace("'", "''") + "'"


def build_rows(csv_path: Path) -> tuple[list[str], Counter[str]]:
    counts: Counter[str] = Counter()
    lines: list[str] = []
    with csv_path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            counts["annonces"] += 1
            name = clean(row["contact_name"])
            phone = clean(row["contact_phone"])
            email = clean(row["contact_email"])
            agency = clean(row["contact_agency"])
            if name is None and phone is None and email is None and agency is None:
                counts["sans contact"] += 1
                continue
            if phone is not None:
                phone = to_international(phone)
                if not PHONE_RE.match(phone):
                    raise ValueError(f"téléphone refusé par la table : {phone!r}")
            if email is not None and not EMAIL_RE.match(email):
                raise ValueError(f"email refusé par la table : {email!r}")
            for text in (name, agency):
                if text is not None and len(text) > MAX_TEXT:
                    raise ValueError(f"texte de plus de {MAX_TEXT} caractères : {text!r}")
            kind = seller_type(clean(row["is_particulier"]) == "True", agency)
            counts[f"seller_type {kind}"] += 1
            counts["contacts"] += 1
            reference = sql_literal(row["reference"])
            values = ", ".join(sql_literal(v) for v in (kind, agency, name, phone, email))
            lines.append(
                "INSERT INTO estate_contact (seller_type, agency_name, contact_name, phone_number, email, id_estate) "
                f"SELECT {values}, id FROM estate WHERE reference = {reference} "
                "ON CONFLICT (id_estate) DO NOTHING;"
            )
    return lines, counts


HEADER = """\
-- ============================================================================
-- 06_populate_estate_contact.sql — GÉNÉRÉ, ne pas modifier à la main.
-- Source : annonces_normalised.csv (dépôt Fil-Rouge, normalised/), par
--   python docker/tools/generate_estate_contact.py <csv>
-- Contact du vendeur de chaque bien importé par 03_populate_estate.sql
-- (ADR-054) : {contacts} lignes pour {annonces} annonces, {sans} annonces
-- sans aucun contact ; seller_type : {private} 'private', {agency} 'agency',
-- {unknown} vides. id_author vide : contacts importés.
-- Chaque ligne retrouve son bien par sa référence : sans 03, elle n'insère rien.
-- ============================================================================

BEGIN;

"""

FOOTER = """
SELECT 'estate_contact' AS tbl, COUNT(*) FROM estate_contact;
COMMIT;
"""


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage : python docker/tools/generate_estate_contact.py <annonces_normalised.csv>")
    lines, counts = build_rows(Path(sys.argv[1]))
    header = HEADER.format(
        contacts=counts["contacts"],
        annonces=counts["annonces"],
        sans=counts["sans contact"],
        private=counts["seller_type private"],
        agency=counts["seller_type agency"],
        unknown=counts["seller_type None"],
    )
    OUTPUT.write_text(header + "\n".join(lines) + "\n" + FOOTER, encoding="utf-8", newline="\n")
    for key in sorted(counts):
        print(f"{key}: {counts[key]}")
    print(f"écrit : {OUTPUT}")


if __name__ == "__main__":
    main()
