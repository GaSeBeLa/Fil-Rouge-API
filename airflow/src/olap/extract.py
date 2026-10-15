"""extract.py — Lire dans l'OLTP ce que l'étoile olap demande, et rien d'autre.

Chantier FLX, fiche FLX6. Une requête par table source ; chacune ne
sélectionne que les colonnes que transform.py utilise (table « colonne olap
-> colonne OLTP » en tête de docker/init-v3/08_olap.sql). RGPD (flux-13) :
aucun prénom, nom, adresse électronique ni numéro d'appel n'est lu, pas même
pour être jeté ensuite.

Reçoit une connexion SQLAlchemy ouverte : la transaction appartient à
l'appelant (le DAG olap_refresh).
"""
from __future__ import annotations

from sqlalchemy import text

QUERIES = {
    "sales": text(
        "SELECT s.id, s.signature_date, s.purchase_amount, s.fees_amount, "
        "s.id_mandate, s.id_estate, p.amount AS payment_amount "
        "FROM sale s LEFT JOIN payment p ON p.id_sale = s.id ORDER BY s.id"
    ),
    "mandates": text(
        "SELECT id, id_mandate_parent, signature_date, is_exclusive, id_hunter, id_client "
        "FROM mandate"
    ),
    "visits": text(
        "SELECT id_mandate, visit_date FROM visit WHERE visitor_type = 'client'"
    ),
    "hunters": text(
        "SELECT id, hire_date, is_hunter_ai, is_carte_t, country_iso FROM hunter"
    ),
    "clients": text(
        "SELECT id, created_at, town, country_iso FROM client"
    ),
    "estates": text(
        "SELECT id, estate_type, typology, surface, nb_rooms, energy_class, "
        "construction_date, id_author IS NULL AS is_imported, "
        "country_iso, postal_code, town FROM estate "
        "WHERE id IN (SELECT id_estate FROM sale)"
    ),
}


def extract(conn) -> dict[str, list[dict[str, object]]]:
    """Les lignes utiles de chaque table, en dictionnaires."""
    return {name: [dict(row._mapping) for row in conn.execute(query)] for name, query in QUERIES.items()}
