"""
test_droits_par_role.py — Fermé par défaut, ouvert table par table (fiche DRO1).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
MATRIX recopie l'annexe d'ADR-027 (`md/adr/adr-027-annexe-matrice-detaillee.md`,
dépôt Fil-Rouge) au niveau du rôle : un rôle a un geste s'il l'a sur au moins
une ligne (« le sien » sera filtré en DRO4 à DRO8). Elle est écrite ici à
la main, pas importée des routeurs : le test juge le code, il ne le relit pas.

- test_refused_role_gets_403 : chaque case fermée rend 403, en lecture (liste
  et ligne), en création et en modification. Le corps envoyé est vide : le
  rôle est jugé avant le corps, donc un rôle autorisé recevrait 422, pas 403.
- test_allowed_role_is_not_refused : chaque case ouverte ne rend pas 403 ;
  un droit fermé par erreur se voit aussi.

- test_payment_calculation_is_admin_only : POST /sales/{id}/payment, le
  calcul du paiement, réservé à l'Admin (DRO2).
============================================================================
"""

from collections.abc import Sequence

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from src.app.utils.roles import ADMIN, ALL_ROLES, CLIENT, HUNTER, MANAGER, READER

from ..conftest import acting_as

A, C, H, M, R = ADMIN, CLIENT, HUNTER, MANAGER, READER

READ, CREATE, UPDATE = "lire", "créer", "modifier"

# préfixe -> (qui lit, qui crée, qui modifie), d'après l'annexe d'ADR-027.
MATRIX: dict[str, tuple[Sequence[str], Sequence[str], Sequence[str]]] = {
    # § 1, les comptes. Le « U le sien » attend DRO5 à DRO7 : Admin seul.
    # Le client crée son compte par POST /search-requests/submit (Q-ACC-12).
    "/roles": ((A, R), (), ()),
    "/users": (ALL_ROLES, (A,), (A,)),
    "/clients": ((A, C, H, R), (C,), (A, C)),
    "/hunters": (ALL_ROLES, (A,), (A,)),
    "/real-estate-managers": ((A, H, M, R), (A,), (A,)),
    # § 2, la demande et le mandat ; criteria : pas de U (versions, point 5).
    "/search-requests": (ALL_ROLES, (C, H), (H, M)),
    "/criteria": (ALL_ROLES, (C, H), ()),
    "/mandates": (ALL_ROLES, (H,), (A, C, H)),
    # § 3, les biens, la sélection, les visites.
    "/estates": (ALL_ROLES, (H, M), (A,)),
    "/pictures": (ALL_ROLES, (H, M), (A,)),
    "/estate-search-requests": ((A, C, H, R), (H,), (H,)),
    "/review-media": ((A, C, H, R), (H,), (H,)),
    "/estate-proposed": ((A, C, H, R), (H,), (C, H)),
    "/visits": (ALL_ROLES, (H,), (A,)),
    # § 4 : la note n'est jamais saisie à la main (ADR-035).
    "/hunter-performances": ((A, H, M, R), (), ()),
    # § 4, l'argent (DRO2). Réglages : Admin seul écrit (Q-ACC-07). Paiement :
    # ni Client ni Reader (point 8), jamais saisi à la main (point 10).
    # Vente : enregistrée par le manager (Q-ACC-03), modifiée par personne.
    "/parameters-fees": ((A, H, M, R), (A,), (A,)),
    "/commission-scales": ((A, H, M, R), (A,), (A,)),
    "/hunter-rate-parameters": ((A, H, M, R), (A,), (A,)),
    "/payments": ((A, H, M), (), (A,)),
    "/sales": (ALL_ROLES, (M,), ()),
    # ADR-054 : ni Client ni Reader.
    "/estate-contacts": ((A, H, M), (A, H, M), (A, H, M)),
}


def cases(allowed: bool) -> list[tuple[str, str, str]]:
    """Les cases (préfixe, geste, rôle) ouvertes (allowed=True) ou fermées."""
    found = []
    for prefix, gestures in MATRIX.items():
        for gesture, roles in zip((READ, CREATE, UPDATE), gestures):
            found += [(prefix, gesture, role) for role in ALL_ROLES if (role in roles) is allowed]
    return found


def act(db_client: TestClient, prefix: str, gesture: str) -> list[Response]:
    """Le geste sur la table, corps vide : seul le rôle est jugé."""
    if gesture == READ:
        return [db_client.get(prefix), db_client.get(f"{prefix}/1")]
    if gesture == CREATE:
        return [db_client.post(prefix, json={})]
    return [db_client.put(f"{prefix}/1", json={})]


def test_every_table_closes_at_least_one_case():
    # Critère de DRO1 : au moins un refus par table.
    refused_tables = {prefix for prefix, _, _ in cases(allowed=False)}
    assert refused_tables == set(MATRIX)


@pytest.mark.parametrize(("prefix", "gesture", "role"), cases(allowed=False))
def test_refused_role_gets_403(db_client: TestClient, prefix: str, gesture: str, role: str):
    with acting_as(role):
        responses = act(db_client, prefix, gesture)
    assert [r.status_code for r in responses] == [403] * len(responses), [r.text for r in responses]


@pytest.mark.parametrize(("prefix", "gesture", "role"), cases(allowed=True))
def test_allowed_role_is_not_refused(db_client: TestClient, prefix: str, gesture: str, role: str):
    with acting_as(role):
        responses = act(db_client, prefix, gesture)
    assert all(r.status_code != 403 for r in responses), [r.text for r in responses]


# Vente inconnue : l'Admin passe le contrôle du rôle et reçoit 404 ; les
# autres sont arrêtés avant, par le rôle.
@pytest.mark.parametrize("role", ALL_ROLES)
def test_payment_calculation_is_admin_only(db_client: TestClient, role: str):
    with acting_as(role):
        response = db_client.post("/sales/999999/payment")
    assert response.status_code == (404 if role == ADMIN else 403), response.text
