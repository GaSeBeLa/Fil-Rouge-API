"""
test_demande_a_prendre.py — Un manager prend une demande que personne ne suit.

Trou trouvé par le test du parcours (test_parcours_particulier.py,
2026-11-19) : une demande déposée par le formulaire n'a ni chasseur ni
manager, et aucune route ne pouvait la confier. Choix B de Sébastien : tout
manager voit les demandes « à prendre » (statut 'confirmed', sans chasseur ni
manager) et en prend une, pour lui seul ; une fois prise, elle est à son
équipe, et les autres managers ne la voient plus.
"""

from typing import Any, Optional

from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlmodel import Session, select

from src.app.models import RealEstateManager, SearchRequest, User, Client
from src.app.utils.roles import MANAGER

from ..conftest import acting_as
from .test_constraints_db import hunter_profile
from .test_le_sien import new_manager

FORM: dict[str, Any] = {
    "email": "a.prendre@exemple.fr",
    "first_name": "Hugo",
    "last_name": "Petit",
    "phone_number": "+33612349999",
    "country_iso": "FR",
    "address": "4 rue des Pyrénées",
    "postal_code": "75020",
    "town": "Paris",
    "budget_max": 250000,
    "estate_type": "Appartement",
}
SEED_MANAGER = 25  # user 25, manager du seed 02 ; ses chasseurs : users 1 à 6
SEED_HUNTER = 1


def _new_request(db_client: TestClient, db_session: Session) -> int:
    """Dépose le formulaire ; l'id de la demande créée, sans chasseur ni manager."""
    assert db_client.post("/search-requests/submit", json=FORM).status_code == 202
    user = db_session.exec(select(User).where(func.lower(User.email) == FORM["email"])).one()
    client = db_session.exec(select(Client).where(Client.id_user == user.id)).one()
    request = db_session.exec(select(SearchRequest).where(SearchRequest.id_client == client.id)).one()
    assert request.id is not None and request.id_hunter is None and request.id_realestatemanager is None
    return request.id


def _profile(db_session: Session, user_id: int) -> Optional[int]:
    return db_session.exec(select(RealEstateManager.id).where(RealEstateManager.id_user == user_id)).one()


def _take(db_client: TestClient, request_id: int, manager_user: int, **changes: Any):
    body = db_client.get(f"/search-requests/{request_id}").json()
    with acting_as(MANAGER, manager_user):
        return db_client.put(f"/search-requests/{request_id}", json={**body, **changes})


def test_every_manager_sees_a_request_nobody_follows(db_client: TestClient, db_session: Session) -> None:
    request_id = _new_request(db_client, db_session)
    other_user, _ = new_manager(db_client, "autre.manager.prendre@exemple.fr")

    for manager_user in (SEED_MANAGER, other_user):
        with acting_as(MANAGER, manager_user):
            assert db_client.get(f"/search-requests/{request_id}").status_code == 200
            assert request_id in [row["id"] for row in db_client.get("/search-requests").json()]


def test_manager_takes_it_and_the_others_lose_it(db_client: TestClient, db_session: Session) -> None:
    request_id = _new_request(db_client, db_session)
    other_user, _ = new_manager(db_client, "autre.manager.perd@exemple.fr")

    taken = _take(db_client, request_id, SEED_MANAGER, id_realestatemanager=_profile(db_session, SEED_MANAGER))

    assert taken.status_code == 200, taken.text
    with acting_as(MANAGER, other_user):
        assert db_client.get(f"/search-requests/{request_id}").status_code == 404


def test_manager_takes_it_and_assigns_his_hunter_at_once(db_client: TestClient, db_session: Session) -> None:
    request_id = _new_request(db_client, db_session)

    taken = _take(
        db_client, request_id, SEED_MANAGER,
        id_realestatemanager=_profile(db_session, SEED_MANAGER), id_hunter=hunter_profile(SEED_HUNTER),
    )

    assert taken.status_code == 200, taken.text
    assert taken.json()["id_hunter"] == hunter_profile(SEED_HUNTER)


def test_manager_cannot_hand_it_to_another_manager(db_client: TestClient, db_session: Session) -> None:
    request_id = _new_request(db_client, db_session)
    _, other_profile = new_manager(db_client, "autre.manager.donne@exemple.fr")

    given = _take(db_client, request_id, SEED_MANAGER, id_realestatemanager=other_profile)

    assert given.status_code in (403, 409), given.text


def test_manager_still_cannot_change_the_status(db_client: TestClient, db_session: Session) -> None:
    request_id = _new_request(db_client, db_session)

    changed = _take(db_client, request_id, SEED_MANAGER, status="rejected")

    assert changed.status_code == 403, changed.text
