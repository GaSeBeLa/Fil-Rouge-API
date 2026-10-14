"""
constraint_messages.py — Le `detail` d'un refus de la base (409), en clair.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Quand PostgreSQL refuse une écriture, psycopg2 dit deux choses utiles
(décision « 409 = phrase + nom », Seb, Discord, 2026-10-14 ; fiche FIN1) :

- la SORTE de refus, par son code SQLSTATE (`exc.orig.pgcode`) :
  23505 valeur en double, 23503 clé étrangère, 23514 CHECK... ;
- le NOM de la contrainte (`exc.orig.diag.constraint_name`), celui du
  schéma `docker/init-v3/01_create_fil_rouge_immobilier.sql`.

`conflict_detail` en fait une phrase : celle de la sorte, ou la phrase
propre d'une contrainte courante (CONSTRAINT_PHRASES), suivie du nom. Le
nom manque : la phrase seule, jamais un message vide.

❌ Jamais la valeur refusée : ni `diag.message_detail`, ni `str(exc.orig)`.
Ils recopient l'email ou l'id d'un autre compte (fuite).
============================================================================
"""

from typing import Optional

from sqlalchemy.exc import IntegrityError

# Codes SQLSTATE de PostgreSQL, classe 23 « Integrity Constraint Violation ».
UNIQUE_VIOLATION = "23505"
FOREIGN_KEY_VIOLATION = "23503"
CHECK_VIOLATION = "23514"
NOT_NULL_VIOLATION = "23502"
EXCLUSION_VIOLATION = "23P01"

SORT_PHRASES = {
    UNIQUE_VIOLATION: "Valeur déjà utilisée : la base refuse un doublon",
    FOREIGN_KEY_VIOLATION: "Référence inexistante : la ligne citée n'existe pas",
    CHECK_VIOLATION: "Valeur refusée par une règle de la base",
    NOT_NULL_VIOLATION: "Champ obligatoire manquant",
    EXCLUSION_VIOLATION: "Chevauchement refusé par la base",
}
DEFAULT_PHRASE = "Écriture refusée par la base"

# Les UNIQUE qu'un formulaire heurte le plus, d'abord l'email du compte.
# Noms relevés dans fil_rouge_test (pg_constraint, pg_indexes) le 2026-10-14.
CONSTRAINT_PHRASES = {
    "user_email_key": "Cet email a déjà un compte",
    "uq_user_email_lower": "Cet email a déjà un compte",
    "client_id_user_key": "Ce compte a déjà sa fiche client",
    "hunter_id_user_key": "Ce compte a déjà sa fiche chasseur",
    "real_estate_manager_id_user_key": "Ce compte a déjà sa fiche manager",
    "role_wording_key": "Ce rôle existe déjà",
    "estate_reference_key": "Cette référence de bien existe déjà",
    "mandate_reference_key": "Cette référence de mandat existe déjà",
    "estate_contact_id_estate_key": "Ce bien a déjà son contact vendeur",
    "uq_estate_search": "Ce bien est déjà retenu pour cette demande",
    "uq_sale_estate": "Ce bien a déjà sa vente",
    "sale_id_mandate_key": "Ce mandat a déjà sa vente",
    "payment_id_sale_key": "Cette vente a déjà son paiement",
    "uq_fees_effective_from": "Une grille d'honoraires commence déjà à cette date",
    "uq_hunter_rate_effective_from": "Des réglages du taux commencent déjà à cette date",
}


def conflict_detail(exc: IntegrityError, deleting: bool) -> str:
    """
    Le `detail` du 409 : une phrase, puis le nom de la contrainte.
    `deleting` : le refus vient d'une suppression (une ligne qui la cite).
    """
    pgcode: Optional[str] = getattr(exc.orig, "pgcode", None)
    name: Optional[str] = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)

    if deleting and pgcode == FOREIGN_KEY_VIOLATION:
        if name:
            return f"Suppression impossible : la ligne est encore référencée par {name}."
        return "Suppression impossible : la ligne est encore référencée ailleurs."

    phrase = CONSTRAINT_PHRASES.get(name or "") or SORT_PHRASES.get(pgcode or "", DEFAULT_PHRASE)
    if name:
        return f"{phrase} (contrainte {name})."
    return f"{phrase}."
