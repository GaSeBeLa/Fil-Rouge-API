"""load.py — Réécrire l'étoile olap en entier, dans la transaction de l'appelant.

Chantier FLX, fiche FLX6. Rejouable : TRUNCATE ... RESTART IDENTITY, puis les
dimensions, puis les faits. Les ids des dimensions sont générés par la base
(GENERATED ALWAYS AS IDENTITY, docker/init-v3/08_olap.sql) ; on les relit par
leur clé naturelle pour remplir les clés étrangères de fait_ventes.

Si une écriture échoue, la transaction (engine.begin() dans le DAG) annule
tout : l'étoile d'hier reste en place, jamais une étoile à moitié vidée.
"""
from __future__ import annotations

from sqlalchemy import text

from src.olap.transform import Row, Star

TABLES = ("fait_ventes", "dim_temps", "dim_chasseur", "dim_client", "dim_bien", "dim_secteur")

DIMENSIONS: dict[str, tuple[str, ...]] = {
    "dim_temps": ("jour", "annee", "trimestre", "mois", "semaine_iso", "jour_semaine_iso"),
    "dim_chasseur": ("id_hunter", "annee_embauche", "est_ia", "a_carte_t", "pays"),
    "dim_client": ("id_client", "annee_inscription", "ville", "pays"),
    "dim_bien": ("id_estate", "type_bien", "typologie", "surface", "nb_pieces",
                 "classe_energie", "annee_construction", "est_importe"),
    "dim_secteur": ("pays", "code_postal", "ville"),
}

# Clé naturelle de chaque dimension, telle que les faits la portent.
NATURAL_KEYS: dict[str, tuple[str, ...]] = {
    "dim_temps": ("jour",),
    "dim_chasseur": ("id_hunter",),
    "dim_client": ("id_client",),
    "dim_bien": ("id_estate",),
    "dim_secteur": ("pays", "code_postal", "ville"),
}

FACT_COLUMNS = ("id_sale", "fk_temps", "fk_chasseur", "fk_client", "fk_bien", "fk_secteur",
                "montant_bien", "honoraires", "commission_chasseur",
                "nb_visites_avant_achat", "delai_semaines", "mandat_exclusif")


def _insert(conn, table: str, columns: tuple[str, ...], rows: list[Row]) -> None:
    if not rows:
        return
    sql = text(f"INSERT INTO olap.{table} ({', '.join(columns)}) "
               f"VALUES ({', '.join(':' + c for c in columns)})")
    conn.execute(sql, [{c: r[c] for c in columns} for r in rows])


def _surrogates(conn, table: str) -> dict[tuple[object, ...], int]:
    """Clé naturelle -> id généré, pour une dimension déjà chargée."""
    key = NATURAL_KEYS[table]
    rows = conn.execute(text(f"SELECT id, {', '.join(key)} FROM olap.{table}"))
    return {tuple(r[1:]): r[0] for r in rows}


def load_star(conn, star: Star) -> dict[str, int]:
    """Vide puis remplit l'étoile ; rend le nombre de lignes écrites par table."""
    conn.execute(text("TRUNCATE " + ", ".join(f"olap.{t}" for t in TABLES) + " RESTART IDENTITY"))
    for table, columns in DIMENSIONS.items():
        _insert(conn, table, columns, getattr(star, table))
    ids = {table: _surrogates(conn, table) for table in DIMENSIONS}

    facts = [{
        **f,
        "fk_temps": ids["dim_temps"][(f["jour"],)],
        "fk_chasseur": ids["dim_chasseur"][(f["id_hunter"],)],
        "fk_client": ids["dim_client"][(f["id_client"],)],
        "fk_bien": ids["dim_bien"][(f["id_estate"],)],
        "fk_secteur": ids["dim_secteur"][(f["pays"], f["code_postal"], f["ville"])],
    } for f in star.facts]
    _insert(conn, "fait_ventes", FACT_COLUMNS, facts)

    counts = {table: len(getattr(star, table)) for table in DIMENSIONS}
    counts["fait_ventes"] = len(facts)
    return counts
