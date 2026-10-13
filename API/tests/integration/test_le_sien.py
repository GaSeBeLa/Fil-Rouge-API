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
from src.app.utils.roles import CLIENT, HUNTER

from ..conftest import acting_as, principal_as
from .conftest import USER_PASSWORD
from .test_constraints_db import (
    ESTATE,
    HUNTER_ID,
    SALE_MANDATE,
    client_payload,
    fees_grid,
    offered_estate,
    payment_payload,
    post_as_hunter,
    post_as_manager,
    write_payment,
)

OTHER_HUNTER_ID = 2  # chasseur du seed 02, comme HUNTER_ID = 1


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
        payment = write_payment(db_session, {**payload, "id_hunter": hunter, "id_sale": sale})
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
    assert {p["id_hunter"] for p in listed} == {HUNTER_ID}


def test_admin_lists_every_payment(db_client: TestClient, payments: tuple[int, int]):
    response = db_client.get("/payments")
    assert response.status_code == 200, response.text
    assert set(payments) <= {p["id"] for p in response.json()}


def test_hunter_reads_his_payment(db_client: TestClient, payments: tuple[int, int]):
    mine, _ = payments
    with acting_as(HUNTER, HUNTER_ID):
        response = db_client.get(f"/payments/{mine}")
    assert response.status_code == 200, response.text
    assert response.json()["id_hunter"] == HUNTER_ID


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
        payment_service.replace_visible(db_session, other, data, principal_as(HUNTER, HUNTER_ID)())

    db_session.refresh(row)
    assert row.model_dump() == before


def test_hunter_update_of_his_payment_passes_the_filter(db_session: Session, payments: tuple[int, int]):
    mine, _ = payments
    row = db_session.get(Payment, mine)
    assert row is not None
    data = Payment.model_validate(row.model_dump())

    updated = payment_service.replace_visible(db_session, mine, data, principal_as(HUNTER, HUNTER_ID)())

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
        "id_hunter": hunter, "id_client": client, "id_search_request": request,
    }
    mandate_id = rows["/mandates"] = created(db_client, "/mandates", mandate, HUNTER, hunter)
    estate = {**ESTATE, "reference": f"TEST-DRO5-{client}"}
    estate_id = rows["/estates"] = created(db_client, "/estates", estate, HUNTER, hunter)
    picture = {"url": "https://exemple.test/p.jpg", "id_estate": estate_id}
    rows["/pictures"] = created(db_client, "/pictures", picture, HUNTER, hunter)
    selection = {"id_estate": estate_id, "id_search_request": request, "id_hunter": hunter}
    review_id = rows["/estate-search-requests"] = created(db_client, "/estate-search-requests", selection, HUNTER, hunter)
    media = {"media_url": "https://exemple.test/a.mp3", "media_type": "audio", "id_estate_searchrequest": review_id}
    rows["/review-media"] = created(db_client, "/review-media", media, HUNTER, hunter)
    offer = {
        "proposition_status": "accepted", "amount_proposition": 350000,
        "id_hunter": hunter, "id_estate": estate_id, "id_mandate": mandate_id,
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


@pytest.mark.parametrize("field", ["id_role", "is_activated"])
def test_client_changes_neither_his_role_nor_his_activation(db_client: TestClient, field: str):
    before = db_client.get(f"/users/{CLIENT_ID}").json()
    # Une autre valeur que la sienne (le client 7 du seed est désactivé).
    change = {"id_role": 4} if field == "id_role" else {"is_activated": not before["is_activated"]}
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
    moved = {**body, "id_client": OTHER_CLIENT_ID, "id_search_request": WORLDS[OTHER_CLIENT_ID][0]}
    with acting_as(CLIENT, CLIENT_ID):
        response = db_client.put(f"/mandates/{mine}", json=moved)

    assert response.status_code == 409, response.text
    assert "le sien" in response.json()["detail"]
    assert db_client.get(f"/mandates/{mine}").json()["id_client"] == CLIENT_ID


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
        mine = db_client.post("/search-requests", json={**body, "id_client": CLIENT_ID})
        theirs = db_client.post("/search-requests", json={**body, "id_client": OTHER_CLIENT_ID})

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
    moved = {**body, "id_mandate": client_rows[OTHER_CLIENT_ID]["/mandates"], "id_hunter": WORLDS[OTHER_CLIENT_ID][1]}
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
        score=Decimal("50.0"), scored_at=datetime(2026, 1, 1, tzinfo=timezone.utc), trigger_type="initial", id_hunter=hunter
    )
    db_session.add(score)
    db_session.commit()
    assert score.id is not None
    rows["/hunter-performances"] = score.id
    scale = {"amount_min": 0, "rate": "0.3000", "valid_from": "2025-01-01", "id_hunter": hunter}
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


def test_hunter_sees_his_manager_not_another(db_client: TestClient):
    account = {"email": "manager.dro6@exemple.fr", "password": USER_PASSWORD, "id_role": MANAGER_ROLE}
    user = db_client.post("/users", json=account)
    assert user.status_code == 201, user.text
    profile = {"id_user": user.json()["id"], "first_name": "Marc", "last_name": "Autre", "phone_number": "+33622222222"}
    other = db_client.post("/real-estate-managers", json=profile)
    assert other.status_code == 201, other.text
    mine = id_where(db_client, "/real-estate-managers", "id_user", SEED_MANAGER)

    with acting_as(HUNTER, HUNTER_ID):
        listed = db_client.get("/real-estate-managers")
        read_mine = db_client.get(f"/real-estate-managers/{mine}")
        read_other = db_client.get(f"/real-estate-managers/{other.json()['id']}")

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
        response = db_client.put(f"/users/{HUNTER_ID}", json={"id_role": 4})

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
            "id_author": client, "id_client": client, "id_hunter": OTHER_HUNTER_ID, "status": "accepted",
        },
        "/criteria": lambda: {
            **without_id(db_client.get(f"/criteria/{rows[HUNTER_ID]['/criteria']}").json()),
            "id_previous_version": None, "id_search_request": request,
        },
        "/mandates": lambda: {
            **SALE_MANDATE, "reference": "TEST-M-DRO6",
            "id_hunter": OTHER_HUNTER_ID, "id_client": client, "id_search_request": request,
        },
        "/estate-search-requests": lambda: {
            "id_estate": rows[HUNTER_ID]["/estates"], "id_search_request": request, "id_hunter": HUNTER_ID,
        },
        "/estate-proposed": lambda: {
            "proposition_status": "proposed", "id_hunter": OTHER_HUNTER_ID,
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
        "id_hunter": HUNTER_ID, "id_client": client, "id_search_request": request,
    }
    with acting_as(HUNTER, HUNTER_ID):
        response = db_client.post("/mandates", json=mandate)
        still_hidden = db_client.get(f"/clients/{their_client}")

    assert response.status_code == 409, response.text
    assert "le sien" in response.json()["detail"]
    assert still_hidden.status_code == 404, still_hidden.text
