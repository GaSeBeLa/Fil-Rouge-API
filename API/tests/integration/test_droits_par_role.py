"""
test_droits_par_role.py — Fermé par défaut, ouvert table par table (fiche DRO1).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
MATRIX recopie l'annexe d'ADR-027 (`md/adr/adr-027-annexe-matrice-detaillee.md`,
dépôt Fil-Rouge) au niveau du rôle : un rôle a un geste s'il l'a sur au moins
une ligne (« le sien » se juge à part : test_le_sien.py). Elle est écrite ici à
la main, pas importée des routeurs : le test juge le code, il ne le relit pas.

- test_refused_role_gets_403 : chaque case fermée rend 403, en lecture (liste
  et ligne), en création et en modification. Le corps envoyé est vide : le
  rôle est jugé avant le corps, donc un rôle autorisé recevrait 422, pas 403.
- test_allowed_role_is_not_refused : chaque case ouverte ne rend pas 403 ;
  un droit fermé par erreur se voit aussi.

- test_payment_calculation_is_admin_only : POST /sales/{id}/payment, le
  calcul du paiement, réservé à l'Admin (DRO2).

Les routes à part (DRO3) : SPECIAL_ROUTES nomme, pour chaque route hors
CRUD, le test qui la juge — le rôle refusé, ou la réponse qui ne fuit rien.
test_every_special_route_is_judged tombe si une route s'ajoute sans y passer.
============================================================================
"""

import importlib
from collections.abc import Sequence

import jwt
import pytest
from fastapi.testclient import TestClient
from httpx import Response

from src.app.main import app
from src.app.models import UserPublic
from src.app.utils.roles import ADMIN, ALL_ROLES, CLIENT, HUNTER, MANAGER, READER

from ..conftest import acting_as
from .conftest import USER_PASSWORD
from .test_demande_avant_compte import FORM, SEED_CLIENT_EMAIL, SUBMIT

A, C, H, M, R = ADMIN, CLIENT, HUNTER, MANAGER, READER

READ, CREATE, UPDATE = "lire", "créer", "modifier"

# préfixe -> (qui lit, qui crée, qui modifie), d'après l'annexe d'ADR-027.
MATRIX: dict[str, tuple[Sequence[str], Sequence[str], Sequence[str]]] = {
    # § 1, les comptes. « U le sien » : le Client depuis DRO5, le Hunter
    # depuis DRO6 ; le Manager attend DRO7. Le client crée son compte par POST
    # /search-requests/submit (Q-ACC-12).
    "/roles": ((A, R), (), ()),
    "/users": (ALL_ROLES, (A,), (A, C, H)),
    "/clients": ((A, C, H, R), (C,), (A, C)),
    "/hunters": (ALL_ROLES, (A,), (A, H)),
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


# --- Les routes à part (DRO3) ---------------------------------------------------

# (méthode, chemin) -> "module.test" qui la juge.
SPECIAL_ROUTES: dict[tuple[str, str], str] = {
    ("GET", "/"): "test_droits_par_role.test_health_check_says_only_its_status",
    ("POST", "/auth/login"): "test_droits_par_role.test_login_gives_only_the_token_of_its_account",
    ("GET", "/auth/me"): "test_droits_par_role.test_me_gives_the_token_account_only",
    ("POST", "/search-requests/submit"): "test_demande_avant_compte.test_same_answer_whoever_the_email",
    ("POST", "/users/{item_id}/anonymize"): "test_anonymisation.test_only_admin_anonymizes",
    ("POST", "/estate-contacts/anonymize-expired"): "test_contact_vendeur.test_only_admin_runs_the_anonymization",
    ("POST", "/sales/{item_id}/payment"): "test_droits_par_role.test_payment_calculation_is_admin_only",
}

# Les quatre routes que build_crud_router pose par table (pas de DELETE, ADR-049).
CRUD_ROUTES = (("GET", ""), ("GET", "/{item_id}"), ("POST", ""), ("PUT", "/{item_id}"))


def test_every_special_route_is_judged():
    # Lu dans le schéma OpenAPI : FastAPI ne déplie plus les routeurs inclus
    # dans app.routes. Aucune route de l'API n'est cachée du schéma.
    routes = {(method.upper(), path) for path, item in app.openapi()["paths"].items() for method in item}
    crud = {(method, prefix + path) for prefix in MATRIX for method, path in CRUD_ROUTES}
    assert crud <= routes
    assert routes - crud == set(SPECIAL_ROUTES)
    for judge in SPECIAL_ROUTES.values():
        module, test = judge.split(".")
        assert hasattr(importlib.import_module(f".{module}", __package__), test), judge


def test_health_check_says_only_its_status():
    # Un client nu, sans clé ni jeton (pas db_client).
    response = TestClient(app).get("/")
    assert response.status_code == 200, response.text
    assert set(response.json()) == {"status", "message"}
    assert response.json()["status"] == "ok"


FIRST_EMAIL, SECOND_EMAIL = "dro3-premier@example.com", "dro3-second@example.com"


@pytest.fixture
def two_accounts(db_client: TestClient) -> tuple[int, int]:
    """Deux comptes Client actifs (rôle 1), créés en Admin ; leurs ids."""
    ids = []
    for email in (FIRST_EMAIL, SECOND_EMAIL):
        account = {"email": email, "password": USER_PASSWORD, "id_role": 1, "is_activated": True}
        response = db_client.post("/users", json=account)
        assert response.status_code == 201, response.text
        ids.append(response.json()["id"])
    return ids[0], ids[1]


def _login(db_client: TestClient, email: str) -> Response:
    return db_client.post("/auth/login", json={"email": email, "password": USER_PASSWORD})


def test_login_gives_only_the_token_of_its_account(db_client: TestClient, two_accounts: tuple[int, int]):
    first, _ = two_accounts
    response = _login(db_client, FIRST_EMAIL)
    assert response.status_code == 200, response.text
    assert set(response.json()) == {"access_token", "token_type", "expires_in"}
    # Le jeton ne porte que l'id du compte et ses dates : ni email, ni rôle.
    claims = jwt.decode(response.json()["access_token"], options={"verify_signature": False})
    assert set(claims) == {"sub", "iat", "exp"}
    assert claims["sub"] == str(first)


def test_me_gives_the_token_account_only(db_client: TestClient, two_accounts: tuple[int, int]):
    first, second = two_accounts
    token = _login(db_client, FIRST_EMAIL).json()["access_token"]
    # Un id glissé dans l'URL ne change rien : le compte vient du jeton.
    for params in ({}, {"id": second, "user_id": second, "id_user": second}):
        response = db_client.get("/auth/me", params=params, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200, response.text
        body = response.json()
        assert (body["id"], body["email"]) == (first, FIRST_EMAIL)
        assert "password" not in body
        assert set(body) == set(UserPublic.model_fields)


# Limite connue (signup_service.py) : les formats ne sont jugés par la base
# que quand une fiche client s'écrit. Ce test passera le jour où elle tombe.
@pytest.mark.xfail(strict=True, reason="Formats jugés par la base seulement pour un email neuf (signup_service.py).")
def test_malformed_form_gets_the_same_answer_whoever_the_email(db_client: TestClient):
    # Téléphone sans indicatif : refusé par le CHECK de client.phone_number.
    malformed = {**FORM, "phone_number": "0612345678"}
    emails = (FORM["email"], SEED_CLIENT_EMAIL)
    answers = {db_client.post(SUBMIT, json={**malformed, "email": email}).status_code for email in emails}
    assert len(answers) == 1, answers
