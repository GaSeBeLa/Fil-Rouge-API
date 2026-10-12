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
from sqlalchemy.exc import IntegrityError, OperationalError
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


# --- P13 : le renouvellement ne contourne plus l'exclusivité -----------------

# Client 7, demande 1, chasseur 1 ; son mandat repris (1) est clos et ne
# bloque rien. Le parent est exclusif, du 2031-01-01 au 2031-07-01.
SIGNED_MANDATE = (
    "INSERT INTO mandate (reference, status, signature_date, ends_at, is_exclusive, "
    "id_hunter, id_client, id_search_request, id_mandate_parent) "
    "VALUES (:ref, 'active', :signed, (CAST(:signed AS date) + INTERVAL '6 months')::date, "
    ":exclusive, :hunter, :client, :request, :parent) RETURNING id"
)


def exclusive_parent(db_session: Session) -> int:
    return run(
        db_session, SIGNED_MANDATE,
        ref="P13-PARENT", signed="2031-01-01", exclusive=True, hunter=1, client=7, request=1, parent=None,
    ).scalar_one()


def test_p13_renewal_in_the_middle_of_an_exclusive_is_refused(db_session: Session):
    parent = exclusive_parent(db_session)
    refused(
        db_session, SIGNED_MANDATE, match="U02",
        ref="P13-MILIEU", signed="2031-03-01", exclusive=True, hunter=2, client=7, request=1, parent=parent,
    )


def test_p13_renewal_at_term_is_accepted(db_session: Session):
    parent = exclusive_parent(db_session)
    run(
        db_session, SIGNED_MANDATE,
        ref="P13-ECHEANCE", signed="2031-07-01", exclusive=True, hunter=1, client=7, request=1, parent=parent,
    )


def test_p13_mandate_as_its_own_parent_is_refused(db_session: Session):
    parent = exclusive_parent(db_session)
    refused(
        db_session,
        "UPDATE mandate SET id_mandate_parent = id WHERE id = :id",
        match="chk_mandate_not_own_parent",
        id=parent,
    )


def test_p13_parent_of_another_client_is_refused(db_session: Session):
    parent = exclusive_parent(db_session)
    refused(
        db_session, SIGNED_MANDATE, match="fk_mandate_parent_same_client",
        ref="P13-AUTRE", signed="2031-07-01", exclusive=False, hunter=3, client=8, request=2, parent=parent,
    )


# --- P15 : deux mandats simultanés ne contournent plus l'exclusivité ---------


def test_p15_second_transaction_waits_for_the_first(db_session: Session):
    # La transaction du test écrit un exclusif du client 7, sans valider. Une
    # seconde connexion qui écrit pour le même client doit attendre son
    # verrou : avec 200 ms de patience, elle abandonne. Rien n'est validé.
    exclusive_parent(db_session)
    engine = db_session.connection().engine
    with engine.connect() as other:
        other.execute(text("SET lock_timeout = '200ms'"))
        with pytest.raises(OperationalError, match="lock timeout"):
            other.execute(
                text(UNSIGNED_MANDATE.replace(":ref", "'P15-B'").replace(":client", "7"))
            )
        other.rollback()


def test_p15_other_client_does_not_wait(db_session: Session):
    exclusive_parent(db_session)
    engine = db_session.connection().engine
    with engine.connect() as other:
        other.execute(text("SET lock_timeout = '200ms'"))
        other.execute(
            text(
                "INSERT INTO mandate (reference, status, is_exclusive, id_hunter, id_client, id_search_request) "
                "VALUES ('P15-C', 'pending_signature', FALSE, 3, 8, 2)"
            )
        )
        other.rollback()


# --- P17 : un bien a deux coordonnées, ou aucune -----------------------------

NEW_ESTATE = (
    "INSERT INTO estate (reference, estate_type, surface, town, latitude, longitude) "
    "VALUES (:ref, 'Maison', 100, 'Montpellier', :lat, :lon)"
)


def test_p17_latitude_without_longitude_is_refused(db_session: Session):
    refused(db_session, NEW_ESTATE, match="chk_estate_coordinates_pair", ref="P17-A", lat=43.61, lon=None)


@pytest.mark.parametrize(("lat", "lon"), [(43.61, 3.88), (None, None)])
def test_p17_both_or_no_coordinates_are_accepted(db_session: Session, lat: Any, lon: Any):
    run(db_session, NEW_ESTATE, ref=f"P17-{lat}", lat=lat, lon=lon)


# --- P22 : une offre vient du chasseur de son mandat --------------------------

# Le mandat 13 est celui du chasseur 2 (02).
NEW_PROPOSAL = (
    "INSERT INTO estate_proposed (proposition_status, id_hunter, id_estate, id_mandate) "
    "VALUES ('proposed', :hunter, :estate, 13)"
)


def new_estate(db_session: Session, ref: str) -> int:
    return run(db_session, NEW_ESTATE + " RETURNING id", ref=ref, lat=None, lon=None).scalar_one()


def test_p22_proposal_by_another_hunter_is_refused(db_session: Session):
    estate = new_estate(db_session, "P22-A")
    refused(db_session, NEW_PROPOSAL, match="fk_proposed_hunter_of_mandate", hunter=3, estate=estate)


def test_p22_proposal_by_the_mandate_hunter_is_accepted(db_session: Session):
    estate = new_estate(db_session, "P22-B")
    run(db_session, NEW_PROPOSAL, hunter=2, estate=estate)


# --- P24 : une visite enregistrée est une visite faite ------------------------

NEW_VISIT = (
    "INSERT INTO visit (visit_date, visitor_type, id_estate, id_mandate) "
    "VALUES (CURRENT_DATE + :days, 'client', :estate, 13)"
)


def test_p24_visit_in_the_future_is_refused(db_session: Session):
    estate = new_estate(db_session, "P24-A")
    refused(db_session, NEW_VISIT, match="chk_visit_not_in_future", days=30, estate=estate)


@pytest.mark.parametrize("days", [-3, 0])
def test_p24_visit_done_is_accepted(db_session: Session, days: int):
    estate = new_estate(db_session, f"P24-{days}")
    run(db_session, NEW_VISIT, days=days, estate=estate)
