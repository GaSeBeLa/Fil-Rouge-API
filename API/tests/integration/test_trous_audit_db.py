"""
test_trous_audit_db.py — Les trous de l'audit (P1 à P36), bouchés en base.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Gabriel a audité le schéma : 36 trous, P1 à P36 (md/journal/problemes-a-regler.md),
vérifiés le 2026-10-12 (md/journal/2026-10-12-verification-audit-problemes.md).
Les choix du groupe sont dans ADR-053. Ici, un bloc par trou bouché en base :

- le cas que le trou laissait passer est maintenant REFUSÉ par PostgreSQL ;
- le cas normal reste ACCEPTÉ, pour prouver que la règle ne bloque pas trop.

Les tests parlent SQL, pas HTTP : la règle tient même sans l'API (un script,
une migration). Chaque refus se joue dans un SAVEPOINT, pour que la
transaction du test reste utilisable ; tout est annulé à la fin (conftest).

Données de départ (posées par init-v3/02) : chasseurs = comptes 1 à 6,
clients = comptes 7 à 24 ; la demande n et le mandat n appartiennent au
client 6 + n ; le mandat 13 (client 19, chasseur 2) est 'active'.
============================================================================
"""

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session  # mère de sqlmodel.Session, la fixture db_session


def run(db_session: Session, sql: str, **params: Any) -> Any:
    return db_session.connection().execute(text(sql), params)


def refused(db_session: Session, sql: str, match: str, **params: Any) -> None:
    """Le SQL doit être refusé par la base, avec un message qui contient `match`."""
    connection = db_session.connection()
    savepoint = connection.begin_nested()
    with pytest.raises(IntegrityError, match=match):
        connection.execute(text(sql), params)
    savepoint.rollback()


def new_user(db_session: Session, email: str) -> int:
    return run(
        db_session,
        "INSERT INTO \"user\" (email, password, id_role) VALUES (:email, 'x', 1) RETURNING id",
        email=email,
    ).scalar_one()


# --- P2 : email unique à la majuscule près, et bien formé ---------------------


def test_p2_same_email_with_other_case_is_refused(db_session: Session):
    new_user(db_session, "Alice@Example.com")
    refused(
        db_session,
        "INSERT INTO \"user\" (email, password, id_role) VALUES ('alice@example.com', 'x', 1)",
        match="uq_user_email_lower",
    )


def test_p2_malformed_email_is_refused(db_session: Session):
    refused(
        db_session,
        "INSERT INTO \"user\" (email, password, id_role) VALUES ('pas-un-email', 'x', 1)",
        match="ck_user_email_format",
    )


def test_p2_two_different_emails_are_accepted(db_session: Session):
    new_user(db_session, "un@exemple.fr")
    new_user(db_session, "deux@exemple.fr")


# --- P6 : une demande qui a reçu une réponse a un chasseur --------------------

NEW_REQUEST = "INSERT INTO search_request (id_author, id_client, id_hunter, status) VALUES (7, 7, {hunter}, '{status}')"


@pytest.mark.parametrize("status", ["accepted", "rejected", "launched"])
def test_p6_answered_request_without_hunter_is_refused(db_session: Session, status: str):
    sql = NEW_REQUEST.format(hunter="NULL", status=status)
    refused(db_session, sql, match="chk_search_request_hunter_after_confirmed")


def test_p6_confirmed_request_without_hunter_is_accepted(db_session: Session):
    run(db_session, NEW_REQUEST.format(hunter="NULL", status="confirmed"))
    run(db_session, NEW_REQUEST.format(hunter=1, status="accepted"))


# --- P8 : une version de critères pointe vers celle d'avant, sur sa demande ---

# Les critères 1 et 2 sont les versions de départ des demandes 1 et 2 (02).
NEW_CRITERIA = (
    "INSERT INTO criteria (estate_type, budget_max, id_author, id_search_request, "
    "id_previous_version, change_reason) "
    "VALUES ('Maison', 300000, 7, :request, :previous, 'budget revu') RETURNING id"
)


def test_p8_next_version_on_same_request_is_accepted(db_session: Session):
    second = run(db_session, NEW_CRITERIA, request=1, previous=1).scalar_one()
    run(db_session, NEW_CRITERIA, request=1, previous=second)


def test_p8_version_of_another_request_is_refused(db_session: Session):
    refused(db_session, NEW_CRITERIA, match="fk_criteria_previous_same_request", request=2, previous=1)


def test_p8_branch_is_refused(db_session: Session):
    run(db_session, NEW_CRITERIA, request=1, previous=1)
    refused(db_session, NEW_CRITERIA, match="uq_criteria_one_successor", request=1, previous=1)


def test_p8_second_first_version_is_refused(db_session: Session):
    refused(db_session, NEW_CRITERIA, match="uq_criteria_one_first_version", request=1, previous=None)


def test_p8_version_pointing_to_itself_is_refused(db_session: Session):
    second = run(db_session, NEW_CRITERIA, request=1, previous=1).scalar_one()
    refused(
        db_session,
        "UPDATE criteria SET id_previous_version = id WHERE id = :id",
        match="chk_criteria_not_own_previous",
        id=second,
    )


# --- P9 : une nouvelle version de critères donne son motif --------------------


def test_p9_next_version_without_reason_is_refused(db_session: Session):
    refused(
        db_session,
        "INSERT INTO criteria (estate_type, budget_max, id_author, id_search_request, id_previous_version) "
        "VALUES ('Maison', 300000, 7, 1, 1)",
        match="chk_criteria_change_reason",
    )


# --- P12 : un mandat appartient au client de sa demande -----------------------

# Pas encore signé : ni durée ni exclusivité à vérifier ici.
UNSIGNED_MANDATE = (
    "INSERT INTO mandate (reference, status, is_exclusive, id_hunter, id_client, id_search_request) "
    "VALUES (:ref, 'pending_signature', FALSE, 1, :client, 1)"
)


def test_p12_mandate_on_another_clients_request_is_refused(db_session: Session):
    # La demande 1 est celle du client 7.
    refused(db_session, UNSIGNED_MANDATE, match="fk_mandate_request_same_client", ref="P12-A", client=8)


def test_p12_mandate_on_own_request_is_accepted(db_session: Session):
    run(db_session, UNSIGNED_MANDATE, ref="P12-B", client=7)
