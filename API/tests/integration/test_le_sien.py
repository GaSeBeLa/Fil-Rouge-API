"""
test_le_sien.py — Le mécanisme « le sien » (ADR-027, point 2 ; fiche DRO4).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Table pilote : payment. Un Hunter ne voit que ses paiements (annexe d'ADR-027,
§ 4, « R les siens », H10) ; celui d'un autre chasseur rend 404, la même
réponse qu'un id qui n'existe pas. L'Admin voit tout.

Le PUT de /payments est réservé à l'Admin (DRO2) : un Hunter y reçoit 403
avant tout filtre (test_droits_par_role.py). Le 404 en modification se prouve
donc au service, par replace_visible, le chemin même du PUT de l'API
(crud_router.py, update_item).

Le Client (fiche DRO5) : deux clients du seed, 7 et 8, ont chacun une ligne
dans les 13 tables de la colonne Client de l'annexe (fixture client_rows).
Chacun liste ses lignes et reçoit 404 sur celles de l'autre, table par
table. En écriture : 404 sur la ligne d'un autre, 409 sur une ligne qui
cesserait d'être à lui, 403 sur son rôle ou son activation.

Le Hunter (fiche DRO6) : deux chasseurs du seed, 1 et 2, ont chacun une ligne
dans les 13 tables où la colonne Hunter dit « le sien » (fixture
hunter_rows) ; même preuve, table par table. Les biens et leurs photos
restent lisibles en entier, le barème par défaut aussi. En écriture : 404
sur la ligne d'un autre, 409 sur une ligne qui serait à un autre, 403 hors de
ses coordonnées (hunter) et sur le média d'une note d'un autre (ADR-051).

Le Manager (fiche DRO7) : le seed n'a qu'un manager ; un second est créé, et
le chasseur 2 passe dans son équipe (fixture team_rows). Chacun voit les
lignes de son équipe dans les 8 tables de sa colonne, ses paiements, son
compte et sa fiche, et reçoit 404 sur celles de l'autre. En écriture : il
n'affecte une demande qu'à l'un de ses chasseurs (409), ne change rien
d'autre (403), n'enregistre une vente que pour son équipe (409).

Compte désactivé (fiche DRO8) : son profil, dans les quatre tables de
données personnelles, n'est plus lu que par l'Admin ; Reader et les autres
rôles reçoivent 404. Les comptes du seed, tous désactivés, sont activés le
temps du test (db_client, tests/integration/conftest.py).
============================================================================
"""

from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from src.app.models import HunterPerformance, Payment
from src.app.routes.payment_router import payment_service
from src.app.utils.exceptions import NotFoundError
from src.app.utils.roles import CLIENT, HUNTER, MANAGER, READER

from ..conftest import acting_as, principal_as
from .conftest import USER_PASSWORD
from .test_constraints_db import (
    ESTATE,
    HUNTER_ID,
    HUNTER_PROFILE,
    SALE_MANDATE,
    client_payload,
    client_profile,
    fees_grid,
    hunter_profile,
    offered_estate,
    payment_payload,
    post_as_hunter,
    post_as_manager,
    write_payment,
)

OTHER_HUNTER_ID = 2  # chasseur du seed 02, comme HUNTER_ID = 1

# Dans ce fichier, HUNTER_ID, CLIENT_ID et leurs « autres » sont des comptes
# (user.id), passés à acting_as. Les colonnes id_hunter et id_client citent
# la fiche (chantier PRF) : hunter_profile() et client_profile() la donnent.


def another_sale(db_client: TestClient, first_sale: int) -> int:
    """Une seconde vente, aux montants de la première, sur un mandat et un bien neufs."""
    mandate = post_as_hunter(db_client, "/mandates", {**SALE_MANDATE, "reference": "TEST-M-VENTE-2"})
    assert mandate.status_code == 201, mandate.text
    mandate_id = mandate.json()["id"]
    first = db_client.get(f"/sales/{first_sale}").json()
    kept = ("signature_date", "purchase_amount", "fees_amount", "sale_origin", "id_parameters_fees")
    sale = {key: first[key] for key in kept}
    sale |= {"id_mandate": mandate_id, "id_estate": offered_estate(db_client, mandate_id, reference="TEST-0002")}
    response = post_as_manager(db_client, "/sales", sale)
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def payments(db_client: TestClient, db_session: Session) -> tuple[int, int]:
    """Un paiement du chasseur 1, un du chasseur 2 ; leurs ids."""
    # La base de test n'a ni vente ni paiement, et une vente ne porte qu'un
    # paiement (payment.id_sale UNIQUE) : il faut deux ventes.
    payload = payment_payload(db_client)
    sales = (payload["id_sale"], another_sale(db_client, payload["id_sale"]))
    ids = []
    for hunter, sale in zip((HUNTER_ID, OTHER_HUNTER_ID), sales):
        payment = write_payment(db_session, {**payload, "id_hunter": hunter_profile(hunter), "id_sale": sale})
        assert payment.id is not None
        ids.append(payment.id)
    return ids[0], ids[1]


def test_hunter_lists_only_his_payments(db_client: TestClient, payments: tuple[int, int]):
    mine, other = payments
    with acting_as(HUNTER, HUNTER_ID):
        response = db_client.get("/payments")
    assert response.status_code == 200, response.text
    listed = response.json()
    assert mine in {p["id"] for p in listed}
    assert other not in {p["id"] for p in listed}
    assert {p["id_hunter"] for p in listed} == {HUNTER_PROFILE}


def test_admin_lists_every_payment(db_client: TestClient, payments: tuple[int, int]):
    response = db_client.get("/payments")
    assert response.status_code == 200, response.text
    assert set(payments) <= {p["id"] for p in response.json()}


def test_hunter_reads_his_payment(db_client: TestClient, payments: tuple[int, int]):
    mine, _ = payments
    with acting_as(HUNTER, HUNTER_ID):
        response = db_client.get(f"/payments/{mine}")
    assert response.status_code == 200, response.text
    assert response.json()["id_hunter"] == HUNTER_PROFILE


def test_hunter_gets_404_on_another_hunter_payment(db_client: TestClient, payments: tuple[int, int]):
    _, other = payments
    with acting_as(HUNTER, HUNTER_ID):
        response = db_client.get(f"/payments/{other}")
        absent = db_client.get("/payments/999999")
    assert response.status_code == 404, response.text
    # Rien ne dit que la ligne existe : même réponse qu'un id absent.
    assert response.json() == absent.json()


def test_hunter_update_of_another_hunter_payment_is_not_found(db_session: Session, payments: tuple[int, int]):
    _, other = payments
    row = db_session.get(Payment, other)
    assert row is not None
    before = row.model_dump()
    data = Payment.model_validate({**before, "amount": "1.00"})

    with pytest.raises(NotFoundError):
        payment_service.replace_visible(db_session, other, data, principal_as(HUNTER, HUNTER_ID, HUNTER_PROFILE)())

    db_session.refresh(row)
    assert row.model_dump() == before


def test_hunter_update_of_his_payment_passes_the_filter(db_session: Session, payments: tuple[int, int]):
    mine, _ = payments
    row = db_session.get(Payment, mine)
    assert row is not None
    data = Payment.model_validate(row.model_dump())

    updated = payment_service.replace_visible(db_session, mine, data, principal_as(HUNTER, HUNTER_ID, HUNTER_PROFILE)())

    assert updated.id == mine


# --- Le Client (DRO5) ---------------------------------------------------------

# Deux clients du seed 02, chacun avec sa demande et son chasseur, sans rien
# en commun : client 7, demande 1, chasseur 1 ; client 8, demande 2, chasseur 3.
CLIENT_ID, OTHER_CLIENT_ID = 7, 8
WORLDS = {CLIENT_ID: (1, HUNTER_ID), OTHER_CLIENT_ID: (2, 3)}

# Les 13 tables de la colonne Client de l'annexe d'ADR-027.
CLIENT_TABLES = [
    "/users", "/clients", "/hunters", "/search-requests", "/criteria", "/mandates", "/estates",
    "/pictures", "/estate-search-requests", "/review-media", "/estate-proposed", "/visits", "/sales",
]


def created(db_client: TestClient, endpoint: str, payload: dict[str, Any], role: str, user_id: int) -> int:
    """POST sous ce compte ; l'id de la ligne créée."""
    with acting_as(role, user_id):
        response = db_client.post(endpoint, json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def id_where(db_client: TestClient, endpoint: str, field: str, value: int) -> int:
    """L'id de la ligne qui a `field == value`, lue par l'Admin."""
    return next(row["id"] for row in db_client.get(endpoint).json() if row[field] == value)


def world(db_client: TestClient, client: int, request: int, hunter: int, grid: int) -> dict[str, int]:
    """Une ligne au client et à son chasseur dans chaque table : celles du seed, puis une vente montée pas à pas."""
    rows = {
        "/users": client,
        "/clients": id_where(db_client, "/clients", "id_user", client),
        "/hunters": id_where(db_client, "/hunters", "id_user", hunter),
        "/search-requests": request,
        "/criteria": id_where(db_client, "/criteria", "id_search_request", request),
    }
    mandate = {
        **SALE_MANDATE, "reference": f"TEST-M-DRO5-{client}",
        "id_hunter": hunter_profile(hunter), "id_client": client_profile(client), "id_search_request": request,
    }
    mandate_id = rows["/mandates"] = created(db_client, "/mandates", mandate, HUNTER, hunter)
    estate = {**ESTATE, "reference": f"TEST-DRO5-{client}"}
    estate_id = rows["/estates"] = created(db_client, "/estates", estate, HUNTER, hunter)
    picture = {"url": "https://exemple.test/p.jpg", "id_estate": estate_id}
    rows["/pictures"] = created(db_client, "/pictures", picture, HUNTER, hunter)
    selection = {"id_estate": estate_id, "id_search_request": request, "id_hunter": hunter_profile(hunter)}
    review_id = rows["/estate-search-requests"] = created(db_client, "/estate-search-requests", selection, HUNTER, hunter)
    media = {"media_url": "https://exemple.test/a.mp3", "media_type": "audio", "id_estate_searchrequest": review_id}
    rows["/review-media"] = created(db_client, "/review-media", media, HUNTER, hunter)
    offer = {
        "proposition_status": "accepted", "amount_proposition": 350000,
        "id_hunter": hunter_profile(hunter), "id_estate": estate_id, "id_mandate": mandate_id,
    }
    rows["/estate-proposed"] = created(db_client, "/estate-proposed", offer, HUNTER, hunter)
    visit = {"visit_date": "2026-02-10", "visitor_type": "client", "id_estate": estate_id, "id_mandate": mandate_id}
    rows["/visits"] = created(db_client, "/visits", visit, HUNTER, hunter)
    sale = {
        "signature_date": "2026-03-01", "purchase_amount": 354712, "fees_amount": "11867.80",
        "sale_origin": "hunter", "id_mandate": mandate_id, "id_estate": estate_id, "id_parameters_fees": grid,
    }
    response = post_as_manager(db_client, "/sales", sale)
    assert response.status_code == 201, response.text
    rows["/sales"] = response.json()["id"]
    return rows


@pytest.fixture
def client_rows(db_client: TestClient) -> dict[int, dict[str, int]]:
    """Par client, l'id de sa ligne dans chacune des 13 tables."""
    grid = fees_grid(db_client)  # une grille pour les deux ventes : sa date d'effet est unique
    return {client: world(db_client, client, *WORLDS[client], grid) for client in WORLDS}


@pytest.mark.parametrize("endpoint", CLIENT_TABLES)
@pytest.mark.parametrize(("me", "other"), [(CLIENT_ID, OTHER_CLIENT_ID), (OTHER_CLIENT_ID, CLIENT_ID)])
def test_client_sees_his_rows_not_the_other_clients(
    db_client: TestClient, client_rows: dict[int, dict[str, int]], endpoint: str, me: int, other: int
):
    mine, theirs = client_rows[me][endpoint], client_rows[other][endpoint]
    with acting_as(CLIENT, me):
        listed = db_client.get(endpoint)
        read_mine = db_client.get(f"{endpoint}/{mine}")
        read_theirs = db_client.get(f"{endpoint}/{theirs}")
        absent = db_client.get(f"{endpoint}/999999")

    assert listed.status_code == 200, listed.text
    listed_ids = {row["id"] for row in listed.json()}
    assert mine in listed_ids
    assert theirs not in listed_ids
    assert read_mine.status_code == 200, read_mine.text
    assert read_theirs.status_code == 404, read_theirs.text
    # Rien ne dit que la ligne existe : même réponse qu'un id absent.
    assert read_theirs.json() == absent.json()


# PRF7 : le rôle protégé est system_role (ADMIN_ONLY_FIELDS), plus id_role.
@pytest.mark.parametrize("field", ["system_role", "is_activated"])
def test_client_changes_neither_his_role_nor_his_activation(db_client: TestClient, field: str):
    before = db_client.get(f"/users/{CLIENT_ID}").json()
    # Une autre valeur que la sienne (activé le temps du test : db_client).
    change = {"system_role": "Admin"} if field == "system_role" else {"is_activated": not before["is_activated"]}
    with acting_as(CLIENT, CLIENT_ID):
        response = db_client.put(f"/users/{CLIENT_ID}", json=change)

    assert response.status_code == 403, response.text
    assert db_client.get(f"/users/{CLIENT_ID}").json() == before


def test_client_updates_his_account_not_another(db_client: TestClient):
    # Renvoyer son propre rôle n'est pas le changer : le corps entier passe.
    with acting_as(CLIENT, CLIENT_ID):
        mine = db_client.put(f"/users/{CLIENT_ID}", json={"email": "alice.dro5@exemple.fr", "id_role": 1})
        theirs = db_client.put(f"/users/{OTHER_CLIENT_ID}", json={"email": "autre.dro5@exemple.fr"})

    assert mine.status_code == 200, mine.text
    assert mine.json()["email"] == "alice.dro5@exemple.fr"
    assert theirs.status_code == 404, theirs.text


def test_client_update_of_another_clients_mandate_returns_404(
    db_client: TestClient, client_rows: dict[int, dict[str, int]]
):
    theirs = client_rows[OTHER_CLIENT_ID]["/mandates"]
    body = db_client.get(f"/mandates/{theirs}").json()
    with acting_as(CLIENT, CLIENT_ID):
        response = db_client.put(f"/mandates/{theirs}", json={**body, "status": "canceled"})

    assert response.status_code == 404, response.text
    assert db_client.get(f"/mandates/{theirs}").json() == body


def test_client_cannot_hand_his_mandate_to_another_client(
    db_client: TestClient, client_rows: dict[int, dict[str, int]]
):
    mine = client_rows[CLIENT_ID]["/mandates"]
    body = db_client.get(f"/mandates/{mine}").json()
    # Avec la demande de l'autre client, la clé (id_search_request, id_client)
    # de la base accepterait : seul le crochet `owns` refuse.
    moved = {**body, "id_client": client_profile(OTHER_CLIENT_ID), "id_search_request": WORLDS[OTHER_CLIENT_ID][0]}
    with acting_as(CLIENT, CLIENT_ID):
        response = db_client.put(f"/mandates/{mine}", json=moved)

    assert response.status_code == 409, response.text
    assert "le sien" in response.json()["detail"]
    assert db_client.get(f"/mandates/{mine}").json()["id_client"] == client_profile(CLIENT_ID)


def test_client_creates_a_client_profile_only_for_himself(db_client: TestClient, create_user: Callable[[str], int]):
    someone = create_user("quelquun.dro5@exemple.fr")
    with acting_as(CLIENT, CLIENT_ID):
        response = db_client.post("/clients", json=client_payload(someone))

    assert response.status_code == 409, response.text
    assert "le sien" in response.json()["detail"]


def without_id(body: dict[str, Any]) -> dict[str, Any]:
    """Une ligne lue, prête à renvoyer en POST : la base choisit id et created_at."""
    return {key: value for key, value in body.items() if key not in ("id", "created_at")}


def test_client_creates_a_search_request_only_for_himself(db_client: TestClient):
    body = without_id(db_client.get(f"/search-requests/{WORLDS[CLIENT_ID][0]}").json())
    with acting_as(CLIENT, CLIENT_ID):
        mine = db_client.post("/search-requests", json={**body, "id_client": client_profile(CLIENT_ID)})
        theirs = db_client.post("/search-requests", json={**body, "id_client": client_profile(OTHER_CLIENT_ID)})

    assert mine.status_code == 201, mine.text
    assert theirs.status_code == 409, theirs.text
    assert "le sien" in theirs.json()["detail"]


def test_client_creates_criteria_only_on_his_request(db_client: TestClient, client_rows: dict[int, dict[str, int]]):
    body = without_id(db_client.get(f"/criteria/{client_rows[CLIENT_ID]['/criteria']}").json())
    other_request = WORLDS[OTHER_CLIENT_ID][0]
    with acting_as(CLIENT, CLIENT_ID):
        response = db_client.post("/criteria", json={**body, "id_previous_version": None, "id_search_request": other_request})

    assert response.status_code == 409, response.text
    assert "le sien" in response.json()["detail"]


def test_client_cannot_move_his_proposal_to_another_clients_mandate(
    db_client: TestClient, client_rows: dict[int, dict[str, int]]
):
    mine = client_rows[CLIENT_ID]["/estate-proposed"]
    body = db_client.get(f"/estate-proposed/{mine}").json()
    moved = {**body, "id_mandate": client_rows[OTHER_CLIENT_ID]["/mandates"], "id_hunter": hunter_profile(WORLDS[OTHER_CLIENT_ID][1])}
    with acting_as(CLIENT, CLIENT_ID):
        response = db_client.put(f"/estate-proposed/{mine}", json=moved)

    assert response.status_code == 409, response.text
    assert "le sien" in response.json()["detail"]
    assert db_client.get(f"/estate-proposed/{mine}").json() == body


# --- Le Hunter (DRO6) ---------------------------------------------------------

# Deux chasseurs du seed 02, chacun avec un client et une demande à lui :
# chasseur 1, client 7, demande 1 ; chasseur 2, client 11, demande 5.
HUNTER_WORLDS = {HUNTER_ID: (7, 1), OTHER_HUNTER_ID: (11, 5)}
SEED_MANAGER = 25  # le seul manager du seed 02, celui des deux chasseurs
MANAGER_ROLE = 3  # id du rôle Manager, table role du seed

# Les 13 tables où la colonne Hunter de l'annexe d'ADR-027 dit « le sien ».
HUNTER_TABLES = [
    "/users", "/clients", "/hunters", "/search-requests", "/criteria", "/mandates", "/estate-search-requests",
    "/review-media", "/estate-proposed", "/visits", "/sales", "/hunter-performances", "/commission-scales",
]


def hunter_world(db_client: TestClient, db_session: Session, hunter: int, grid: int) -> dict[str, int]:
    """Une ligne au chasseur dans chacune des 13 tables, et un bien avec sa photo."""
    client, request = HUNTER_WORLDS[hunter]
    rows = world(db_client, client, request, hunter, grid) | {"/users": hunter}
    # POST /hunter-performances est fermé à tous : une note naît du calcul (H12).
    score = HunterPerformance(
        score=Decimal("50.0"), scored_at=datetime(2026, 1, 1, tzinfo=timezone.utc), trigger_type="initial",
        id_hunter=hunter_profile(hunter),
    )
    db_session.add(score)
    db_session.commit()
    assert score.id is not None
    rows["/hunter-performances"] = score.id
    scale = {"amount_min": 0, "rate": "0.3000", "valid_from": "2025-01-01", "id_hunter": hunter_profile(hunter)}
    response = db_client.post("/commission-scales", json=scale)
    assert response.status_code == 201, response.text
    rows["/commission-scales"] = response.json()["id"]
    return rows


@pytest.fixture
def hunter_rows(db_client: TestClient, db_session: Session) -> dict[int, dict[str, int]]:
    """Par chasseur, l'id de sa ligne dans chacune des 13 tables, plus un bien et sa photo."""
    grid = fees_grid(db_client)
    return {hunter: hunter_world(db_client, db_session, hunter, grid) for hunter in HUNTER_WORLDS}


@pytest.mark.parametrize("endpoint", HUNTER_TABLES)
@pytest.mark.parametrize(("me", "other"), [(HUNTER_ID, OTHER_HUNTER_ID), (OTHER_HUNTER_ID, HUNTER_ID)])
def test_hunter_sees_his_rows_not_the_other_hunters(
    db_client: TestClient, hunter_rows: dict[int, dict[str, int]], endpoint: str, me: int, other: int
):
    mine, theirs = hunter_rows[me][endpoint], hunter_rows[other][endpoint]
    with acting_as(HUNTER, me):
        listed = db_client.get(endpoint)
        read_mine = db_client.get(f"{endpoint}/{mine}")
        read_theirs = db_client.get(f"{endpoint}/{theirs}")
        absent = db_client.get(f"{endpoint}/999999")

    assert listed.status_code == 200, listed.text
    listed_ids = {row["id"] for row in listed.json()}
    assert mine in listed_ids
    assert theirs not in listed_ids
    assert read_mine.status_code == 200, read_mine.text
    assert read_theirs.status_code == 404, read_theirs.text
    assert read_theirs.json() == absent.json()


@pytest.mark.parametrize("endpoint", ["/estates", "/pictures"])
def test_hunter_reads_every_estate_and_picture(
    db_client: TestClient, hunter_rows: dict[int, dict[str, int]], endpoint: str
):
    # Les biens restent lisibles en entier (H2, H5) : pas de « le sien » ici.
    with acting_as(HUNTER, HUNTER_ID):
        response = db_client.get(f"{endpoint}/{hunter_rows[OTHER_HUNTER_ID][endpoint]}")
    assert response.status_code == 200, response.text


def test_hunter_sees_the_default_scale(db_client: TestClient):
    default = {"amount_min": 0, "rate": "0.3000", "valid_from": "2025-01-01"}
    created_scale = db_client.post("/commission-scales", json=default)
    assert created_scale.status_code == 201, created_scale.text
    scale_id = created_scale.json()["id"]

    with acting_as(HUNTER, HUNTER_ID):
        listed = db_client.get("/commission-scales")
        read = db_client.get(f"/commission-scales/{scale_id}")

    assert scale_id in {row["id"] for row in listed.json()}
    assert read.status_code == 200, read.text


def new_manager(db_client: TestClient, email: str) -> tuple[int, int]:
    """Un second manager, créé par l'Admin : l'id de son compte, celui de sa fiche."""
    account = {"email": email, "password": USER_PASSWORD, "id_role": MANAGER_ROLE}
    user = db_client.post("/users", json=account)
    assert user.status_code == 201, user.text
    profile = {"id_user": user.json()["id"], "first_name": "Marc", "last_name": "Autre", "phone_number": "+33622222222"}
    created_profile = db_client.post("/real-estate-managers", json=profile)
    assert created_profile.status_code == 201, created_profile.text
    return user.json()["id"], created_profile.json()["id"]


def test_hunter_sees_his_manager_not_another(db_client: TestClient):
    _, other = new_manager(db_client, "manager.dro6@exemple.fr")
    mine = id_where(db_client, "/real-estate-managers", "id_user", SEED_MANAGER)

    with acting_as(HUNTER, HUNTER_ID):
        listed = db_client.get("/real-estate-managers")
        read_mine = db_client.get(f"/real-estate-managers/{mine}")
        read_other = db_client.get(f"/real-estate-managers/{other}")

    assert {row["id"] for row in listed.json()} == {mine}
    assert read_mine.status_code == 200, read_mine.text
    assert read_other.status_code == 404, read_other.text


def test_hunter_changes_his_contact_details(db_client: TestClient):
    mine = id_where(db_client, "/hunters", "id_user", HUNTER_ID)
    body = db_client.get(f"/hunters/{mine}").json()
    with acting_as(HUNTER, HUNTER_ID):
        response = db_client.put(f"/hunters/{mine}", json={**body, "phone_number": "+33633333333"})

    assert response.status_code == 200, response.text
    assert response.json()["phone_number"] == "+33633333333"


@pytest.mark.parametrize("field", ["hire_date", "id_realestatemanager", "is_carte_t"])
def test_hunter_changes_nothing_but_his_contact_details(db_client: TestClient, field: str):
    mine = id_where(db_client, "/hunters", "id_user", HUNTER_ID)
    body = db_client.get(f"/hunters/{mine}").json()
    other_value = {"hire_date": "2019-01-02", "id_realestatemanager": 999, "is_carte_t": not body["is_carte_t"]}
    with acting_as(HUNTER, HUNTER_ID):
        response = db_client.put(f"/hunters/{mine}", json={**body, field: other_value[field]})

    assert response.status_code == 403, response.text
    assert db_client.get(f"/hunters/{mine}").json() == body


def test_hunter_changes_neither_his_role_nor_his_activation(db_client: TestClient):
    before = db_client.get(f"/users/{HUNTER_ID}").json()
    with acting_as(HUNTER, HUNTER_ID):
        response = db_client.put(f"/users/{HUNTER_ID}", json={"system_role": "Admin"})  # PRF7

    assert response.status_code == 403, response.text
    assert db_client.get(f"/users/{HUNTER_ID}").json() == before


@pytest.mark.parametrize(
    "endpoint",
    ["/users", "/hunters", "/search-requests", "/mandates", "/estate-search-requests", "/review-media", "/estate-proposed"],
)
def test_hunter_update_of_another_hunters_row_returns_404(
    db_client: TestClient, hunter_rows: dict[int, dict[str, int]], endpoint: str
):
    theirs = hunter_rows[OTHER_HUNTER_ID][endpoint]
    before = db_client.get(f"{endpoint}/{theirs}").json()
    body = {"email": "autre.dro6@exemple.fr"} if endpoint == "/users" else before
    with acting_as(HUNTER, HUNTER_ID):
        response = db_client.put(f"{endpoint}/{theirs}", json=body)

    assert response.status_code == 404, response.text
    assert db_client.get(f"{endpoint}/{theirs}").json() == before


def other_hunters_line(db_client: TestClient, rows: dict[int, dict[str, int]], endpoint: str) -> dict[str, Any]:
    """Une ligne qu'écrirait le chasseur 1, mais qui serait au chasseur 2."""
    client, request = HUNTER_WORLDS[OTHER_HUNTER_ID]
    theirs = rows[OTHER_HUNTER_ID]
    lines: dict[str, Callable[[], dict[str, Any]]] = {
        "/search-requests": lambda: {
            "id_author": client, "id_client": client_profile(client), "id_hunter": hunter_profile(OTHER_HUNTER_ID),
            "status": "accepted",
        },
        "/criteria": lambda: {
            **without_id(db_client.get(f"/criteria/{rows[HUNTER_ID]['/criteria']}").json()),
            "id_previous_version": None, "id_search_request": request,
        },
        "/mandates": lambda: {
            **SALE_MANDATE, "reference": "TEST-M-DRO6",
            "id_hunter": hunter_profile(OTHER_HUNTER_ID), "id_client": client_profile(client), "id_search_request": request,
        },
        "/estate-search-requests": lambda: {
            "id_estate": rows[HUNTER_ID]["/estates"], "id_search_request": request, "id_hunter": HUNTER_PROFILE,
        },
        "/estate-proposed": lambda: {
            "proposition_status": "proposed", "id_hunter": hunter_profile(OTHER_HUNTER_ID),
            "id_estate": theirs["/estates"], "id_mandate": theirs["/mandates"],
        },
        "/visits": lambda: {
            "visit_date": "2026-02-10", "visitor_type": "hunter",
            "id_estate": theirs["/estates"], "id_mandate": theirs["/mandates"],
        },
    }
    return lines[endpoint]()


@pytest.mark.parametrize(
    "endpoint", ["/search-requests", "/criteria", "/mandates", "/estate-search-requests", "/estate-proposed", "/visits"]
)
def test_hunter_creates_only_his_rows(db_client: TestClient, hunter_rows: dict[int, dict[str, int]], endpoint: str):
    payload = other_hunters_line(db_client, hunter_rows, endpoint)
    with acting_as(HUNTER, HUNTER_ID):
        response = db_client.post(endpoint, json=payload)

    assert response.status_code == 409, response.text
    assert "le sien" in response.json()["detail"]


def test_hunter_cannot_move_his_media_to_another_hunters_review(
    db_client: TestClient, hunter_rows: dict[int, dict[str, int]]
):
    mine = hunter_rows[HUNTER_ID]["/review-media"]
    body = db_client.get(f"/review-media/{mine}").json()
    moved = {**body, "id_estate_searchrequest": hunter_rows[OTHER_HUNTER_ID]["/estate-search-requests"]}
    with acting_as(HUNTER, HUNTER_ID):
        response = db_client.put(f"/review-media/{mine}", json=moved)

    assert response.status_code == 403, response.text
    assert "ADR-051" in response.json()["detail"]
    assert db_client.get(f"/review-media/{mine}").json() == body


def test_hunter_cannot_erase_a_field_by_leaving_it_out(db_client: TestClient):
    # Relecture DRO6 : le PUT remplace toute la ligne ; un champ réservé omis
    # du corps y vaudrait son défaut, None.
    mine = id_where(db_client, "/hunters", "id_user", HUNTER_ID)
    profile = db_client.get(f"/hunters/{mine}").json()
    certified = {**profile, "certification_date": "2024-05-01", "is_carte_t": True, "education_level": "bac+5"}
    set_by_admin = db_client.put(f"/hunters/{mine}", json=certified)
    assert set_by_admin.status_code == 200, set_by_admin.text
    before = set_by_admin.json()
    reserved = ("certification_date", "is_carte_t", "education_level", "is_hunter_ai", "company_name", "id", "created_at")
    short = {key: value for key, value in before.items() if key not in reserved}

    with acting_as(HUNTER, HUNTER_ID):
        response = db_client.put(f"/hunters/{mine}", json=short)

    assert response.status_code == 403, response.text
    assert db_client.get(f"/hunters/{mine}").json() == before


def test_hunter_cannot_sign_a_mandate_on_another_hunters_request(
    db_client: TestClient, hunter_rows: dict[int, dict[str, int]]
):
    # Relecture DRO6 : un mandat à son nom sur la demande d'un autre lui
    # ouvrait le client de cet autre (H3).
    client, request = HUNTER_WORLDS[OTHER_HUNTER_ID]
    their_client = hunter_rows[OTHER_HUNTER_ID]["/clients"]
    mandate = {
        **SALE_MANDATE, "reference": "TEST-M-DRO6-B",
        "id_hunter": HUNTER_PROFILE, "id_client": client_profile(client), "id_search_request": request,
    }
    with acting_as(HUNTER, HUNTER_ID):
        response = db_client.post("/mandates", json=mandate)
        still_hidden = db_client.get(f"/clients/{their_client}")

    assert response.status_code == 409, response.text
    assert "le sien" in response.json()["detail"]
    assert still_hidden.status_code == 404, still_hidden.text


# --- Le Manager (DRO7) --------------------------------------------------------

# Le seed 02 n'a qu'un manager, 25, celui des six chasseurs (compté le
# 13/10 dans fil_rouge_test). Un second manager est créé ; le chasseur 2 passe
# dans son équipe, une fois ses lignes posées (la vente du chasseur 2 est
# enregistrée par le manager 25, qui ne le pourrait plus après).
SEED, NEW = "seed", "new"

# Les 8 tables où la colonne Manager de l'annexe d'ADR-027 dit « son équipe ».
TEAM_TABLES = [
    "/hunters", "/search-requests", "/criteria", "/mandates", "/visits", "/sales",
    "/hunter-performances", "/commission-scales",
]


def move_hunter(db_client: TestClient, hunter: int, manager: int) -> None:
    """L'Admin passe le chasseur dans l'équipe de ce manager (deux comptes)."""
    profile_id = id_where(db_client, "/hunters", "id_user", hunter)
    manager_id = id_where(db_client, "/real-estate-managers", "id_user", manager)
    body = db_client.get(f"/hunters/{profile_id}").json()
    response = db_client.put(f"/hunters/{profile_id}", json={**body, "id_realestatemanager": manager_id})
    assert response.status_code == 200, response.text


@pytest.fixture
def other_manager(db_client: TestClient) -> int:
    """Un second manager ; l'id de son compte."""
    user_id, _ = new_manager(db_client, "manager.dro7@exemple.fr")
    return user_id


@pytest.fixture
def team_rows(
    db_client: TestClient, hunter_rows: dict[int, dict[str, int]], other_manager: int
) -> dict[str, tuple[int, dict[str, int]]]:
    """Par manager : son compte, et les lignes d'un chasseur de son équipe (1 pour le seed, 2 pour l'autre)."""
    move_hunter(db_client, OTHER_HUNTER_ID, other_manager)
    return {SEED: (SEED_MANAGER, hunter_rows[HUNTER_ID]), NEW: (other_manager, hunter_rows[OTHER_HUNTER_ID])}


@pytest.mark.parametrize("endpoint", TEAM_TABLES)
@pytest.mark.parametrize(("me", "other"), [(SEED, NEW), (NEW, SEED)])
def test_manager_sees_his_team_not_the_other_team(
    db_client: TestClient, team_rows: dict[str, tuple[int, dict[str, int]]], endpoint: str, me: str, other: str
):
    manager, rows = team_rows[me]
    mine, theirs = rows[endpoint], team_rows[other][1][endpoint]
    with acting_as(MANAGER, manager):
        listed = db_client.get(endpoint)
        read_mine = db_client.get(f"{endpoint}/{mine}")
        read_theirs = db_client.get(f"{endpoint}/{theirs}")
        absent = db_client.get(f"{endpoint}/999999")

    assert listed.status_code == 200, listed.text
    listed_ids = {row["id"] for row in listed.json()}
    assert mine in listed_ids
    assert theirs not in listed_ids
    assert read_mine.status_code == 200, read_mine.text
    assert read_theirs.status_code == 404, read_theirs.text
    assert read_theirs.json() == absent.json()


def test_manager_sees_his_hunters_payments_not_the_other_teams(
    db_client: TestClient, payments: tuple[int, int], other_manager: int
):
    # Q-ACC-02 : « ceux de ses chasseurs ». Le paiement du chasseur 2 passe
    # avec lui dans l'autre équipe.
    move_hunter(db_client, OTHER_HUNTER_ID, other_manager)
    of_hunter_1, of_hunter_2 = payments
    seen: dict[int, tuple[set[int], int, int]] = {}
    for manager in (SEED_MANAGER, other_manager):
        with acting_as(MANAGER, manager):
            listed = {row["id"] for row in db_client.get("/payments").json()}
            seen[manager] = (
                listed,
                db_client.get(f"/payments/{of_hunter_1}").status_code,
                db_client.get(f"/payments/{of_hunter_2}").status_code,
            )

    assert of_hunter_1 in seen[SEED_MANAGER][0] and of_hunter_2 not in seen[SEED_MANAGER][0]
    assert seen[SEED_MANAGER][1:] == (200, 404)
    assert seen[other_manager][0] == {of_hunter_2}
    assert seen[other_manager][1:] == (404, 200)


def test_manager_sees_only_his_account_and_profile(db_client: TestClient, other_manager: int):
    mine = id_where(db_client, "/real-estate-managers", "id_user", SEED_MANAGER)
    theirs = id_where(db_client, "/real-estate-managers", "id_user", other_manager)
    with acting_as(MANAGER, SEED_MANAGER):
        users = {row["id"] for row in db_client.get("/users").json()}
        other_user = db_client.get(f"/users/{other_manager}")
        profiles = {row["id"] for row in db_client.get("/real-estate-managers").json()}
        other_profile = db_client.get(f"/real-estate-managers/{theirs}")

    assert users == {SEED_MANAGER}
    assert other_user.status_code == 404, other_user.text
    assert profiles == {mine}
    assert other_profile.status_code == 404, other_profile.text


def test_manager_changes_his_contact_details_and_nothing_else(db_client: TestClient, other_manager: int):
    mine = id_where(db_client, "/real-estate-managers", "id_user", SEED_MANAGER)
    theirs = id_where(db_client, "/real-estate-managers", "id_user", other_manager)
    body = db_client.get(f"/real-estate-managers/{mine}").json()
    their_body = db_client.get(f"/real-estate-managers/{theirs}").json()
    with acting_as(MANAGER, SEED_MANAGER):
        phone = db_client.put(f"/real-estate-managers/{mine}", json={**body, "phone_number": "+33644444444"})
        account = db_client.put(f"/real-estate-managers/{mine}", json={**body, "id_user": other_manager})
        other = db_client.put(f"/real-estate-managers/{theirs}", json=their_body)

    assert phone.status_code == 200, phone.text
    assert phone.json()["phone_number"] == "+33644444444"
    assert account.status_code == 403, account.text
    assert other.status_code == 404, other.text
    assert db_client.get(f"/real-estate-managers/{theirs}").json() == their_body


def test_manager_updates_his_account_but_not_his_role(db_client: TestClient, other_manager: int):
    before = db_client.get(f"/users/{SEED_MANAGER}").json()
    with acting_as(MANAGER, SEED_MANAGER):
        mine = db_client.put(f"/users/{SEED_MANAGER}", json={"email": "manager.25.dro7@exemple.fr"})
        role = db_client.put(f"/users/{SEED_MANAGER}", json={"system_role": "Admin"})  # PRF7
        theirs = db_client.put(f"/users/{other_manager}", json={"email": "autre.dro7@exemple.fr"})

    assert mine.status_code == 200, mine.text
    assert role.status_code == 403, role.text
    assert theirs.status_code == 404, theirs.text
    assert db_client.get(f"/users/{SEED_MANAGER}").json()["system_role"] == before["system_role"]


def test_manager_assigns_a_request_to_one_of_his_hunters_only(
    db_client: TestClient, team_rows: dict[str, tuple[int, dict[str, int]]]
):
    # Q-ACC-10 : affecter un chasseur. Le chasseur 3 est resté au manager 25.
    mine, theirs = team_rows[SEED][1]["/search-requests"], team_rows[NEW][1]["/search-requests"]
    body = db_client.get(f"/search-requests/{mine}").json()
    their_body = db_client.get(f"/search-requests/{theirs}").json()
    with acting_as(MANAGER, SEED_MANAGER):
        to_other_team = db_client.put(f"/search-requests/{mine}", json={**body, "id_hunter": hunter_profile(OTHER_HUNTER_ID)})
        status = db_client.put(f"/search-requests/{mine}", json={**body, "status": "rejected"})
        their_request = db_client.put(f"/search-requests/{theirs}", json={**their_body, "id_hunter": hunter_profile(3)})
        assigned = db_client.put(f"/search-requests/{mine}", json={**body, "id_hunter": hunter_profile(3)})

    assert to_other_team.status_code == 409, to_other_team.text
    assert "le sien" in to_other_team.json()["detail"]
    assert status.status_code == 403, status.text
    assert their_request.status_code == 404, their_request.text
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["id_hunter"] == hunter_profile(3)
    assert db_client.get(f"/search-requests/{theirs}").json() == their_body


def test_manager_records_a_sale_only_for_his_team(
    db_client: TestClient, team_rows: dict[str, tuple[int, dict[str, int]]]
):
    # Q-ACC-03 : une vente de son équipe. Celle du chasseur 2, renvoyée par le
    # manager 25, porte sur un mandat de l'autre équipe : refusée avant tout
    # contrôle de la vente elle-même.
    theirs = db_client.get(f"/sales/{team_rows[NEW][1]['/sales']}").json()
    with acting_as(MANAGER, SEED_MANAGER):
        response = db_client.post("/sales", json=without_id(theirs))

    assert response.status_code == 409, response.text
    assert "le sien" in response.json()["detail"]


# --- Compte désactivé (DRO8) --------------------------------------------------

# ADR-027, point 7 : le profil d'un compte désactivé n'est plus lu que par
# l'Admin. Par table : un compte, et un lecteur qui le voit tant qu'il est
# actif (Reader voit tout ; le chasseur 3 suit la demande 2 du client 8 ; le
# manager 25 mène le chasseur 2 ; le chasseur 1 a pour manager le 25).
DEACTIVATED_PROFILES = [
    ("/users", OTHER_CLIENT_ID, READER, 0),
    ("/clients", OTHER_CLIENT_ID, READER, 0),
    ("/clients", OTHER_CLIENT_ID, HUNTER, 3),
    ("/hunters", OTHER_HUNTER_ID, READER, 0),
    ("/hunters", OTHER_HUNTER_ID, MANAGER, SEED_MANAGER),
    ("/real-estate-managers", SEED_MANAGER, READER, 0),
    ("/real-estate-managers", SEED_MANAGER, HUNTER, HUNTER_ID),
]


def deactivate(db_client: TestClient, account: int) -> None:
    """L'Admin désactive le compte (ADR-049, Décision 1)."""
    response = db_client.put(f"/users/{account}", json={"is_activated": False})
    assert response.status_code == 200, response.text


def profile_of(db_client: TestClient, endpoint: str, account: int) -> int:
    """L'id de la ligne de ce compte dans la table, lue par l'Admin."""
    return account if endpoint == "/users" else id_where(db_client, endpoint, "id_user", account)


@pytest.mark.parametrize(("endpoint", "account", "role", "viewer"), DEACTIVATED_PROFILES)
def test_deactivated_profile_is_read_by_admin_only(
    db_client: TestClient, endpoint: str, account: int, role: str, viewer: int
):
    row = profile_of(db_client, endpoint, account)
    with acting_as(role, viewer):
        before = db_client.get(f"{endpoint}/{row}")
    assert before.status_code == 200, before.text  # actif, le lecteur le voit

    deactivate(db_client, account)
    with acting_as(role, viewer):
        listed = {item["id"] for item in db_client.get(endpoint).json()}
        after = db_client.get(f"{endpoint}/{row}")
        absent = db_client.get(f"{endpoint}/999999")
    by_admin = db_client.get(f"{endpoint}/{row}")

    assert after.status_code == 404, after.text
    assert after.json() == absent.json()
    assert row not in listed
    assert by_admin.status_code == 200, by_admin.text


def test_rows_citing_a_deactivated_account_stay_readable(db_client: TestClient):
    # Seul le profil se cache : la demande 2 du client 8 reste lisible.
    deactivate(db_client, OTHER_CLIENT_ID)
    with acting_as(READER, 0):
        request = db_client.get(f"/search-requests/{WORLDS[OTHER_CLIENT_ID][0]}")

    assert request.status_code == 200, request.text
    assert request.json()["id_client"] == client_profile(OTHER_CLIENT_ID)
