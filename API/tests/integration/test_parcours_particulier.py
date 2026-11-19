"""
test_parcours_particulier.py — Test fonctionnel : le parcours du particulier, de bout en bout.

Le plan de tests du sujet veut des tests « unitaires + fonctionnels »
(GRILLE-EVALUATION.md). Les autres tests prouvent une règle à la fois ; celui-ci
enchaîne les user stories 01 et 02 dans l'ordre où un particulier les vit :

1. il dépose sa demande sur le site, sans compte (01, @formulaire) ;
2. sa demande est confiée à un manager, qui lui affecte un chasseur ; le
   chasseur l'accepte (01, @affectation ; 04, @acceptation) ;
3. le manager obtient son code d'activation, le particulier choisit son mot
   de passe et se connecte avec un VRAI jeton (01, @creation-compte) ;
4. le chasseur signe le mandat, garde un bien et le lui propose (01,
   @signature-mandat ; 02, @propositions) ;
5. le particulier voit la proposition et dit qu'il est intéressé (02,
   @bien-retenu).

Les étapes du particulier passent par le vrai contrôle du jeton : le
remplaçant `get_principal` de db_client est retiré pour elles.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlmodel import Session, select

from src.app.main import app
from src.app.models import Client, RealEstateManager, SearchRequest, User
from src.app.utils.roles import HUNTER, MANAGER, get_principal

from ..conftest import acting_as
from .test_constraints_db import ESTATE, hunter_profile

FORM: dict[str, Any] = {
    "email": "parcours.complet@exemple.fr",
    "first_name": "Nina",
    "last_name": "Leroy",
    "phone_number": "+33612340000",
    "country_iso": "FR",
    "address": "8 rue Oberkampf",
    "postal_code": "75011",
    "town": "Paris",
    "budget_max": 400000,
    "estate_type": "Appartement",
}
PASSWORD = "mon-mot-de-passe-a-moi"
SEED_HUNTER = 1  # user 1, chasseur du seed 02
SEED_MANAGER = 25  # user 25, manager du seed 02


@contextmanager
def real_token() -> Iterator[None]:
    """Le temps du bloc, le jeton est vraiment contrôlé (plus de compte simulé)."""
    previous = app.dependency_overrides.pop(get_principal)
    try:
        yield
    finally:
        app.dependency_overrides[get_principal] = previous


def _created(response) -> int:
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_particulier_from_form_to_interest(db_client: TestClient, db_session: Session) -> None:
    # 1. La demande, déposée sans compte.
    with real_token():
        assert db_client.post("/search-requests/submit", json=FORM).status_code == 202
    user = db_session.exec(select(User).where(func.lower(User.email) == FORM["email"])).one()
    client = db_session.exec(select(Client).where(Client.id_user == user.id)).one()
    request = db_session.exec(select(SearchRequest).where(SearchRequest.id_client == client.id)).one()
    assert user.is_activated is False and request.status == "confirmed"

    # 2. La demande est confiée au manager, qui affecte un chasseur ; le
    #    chasseur l'accepte.
    #    ⚠️ TROU trouvé par ce test (2026-11-19) : aucune route ne confie une
    #    demande neuve à un manager (l'Admin lit seulement, le Manager ne change
    #    que id_hunter, et ne voit pas une demande sans équipe). Ce seul pas
    #    passe donc par la base, en attendant le choix du groupe.
    manager = db_session.exec(select(RealEstateManager).where(RealEstateManager.id_user == SEED_MANAGER)).one()
    request.id_realestatemanager = manager.id
    db_session.add(request)
    db_session.commit()
    body = db_client.get(f"/search-requests/{request.id}").json()
    with acting_as(MANAGER, SEED_MANAGER):
        assigned = db_client.put(f"/search-requests/{request.id}", json={**body, "id_hunter": hunter_profile(SEED_HUNTER)})
    assert assigned.status_code == 200, assigned.text
    with acting_as(HUNTER, SEED_HUNTER):
        accepted = db_client.put(f"/search-requests/{request.id}", json={**assigned.json(), "status": "accepted"})
    assert accepted.status_code == 200, accepted.text

    # 3. Le manager obtient le code ; le particulier pose son mot de passe, puis se connecte.
    with acting_as(MANAGER, SEED_MANAGER):
        issued = db_client.post(f"/users/{user.id}/activation-code")
    assert issued.status_code == 200, issued.text
    with real_token():
        activated = db_client.post("/auth/activate", json={"code": issued.json()["code"], "password": PASSWORD})
        assert activated.status_code == 200, activated.text
        login = db_client.post("/auth/login", json={"email": FORM["email"], "password": PASSWORD})
        assert login.status_code == 200, login.text
    as_client = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # 4. Le chasseur signe le mandat, garde un bien et le propose.
    with acting_as(HUNTER, SEED_HUNTER):
        mandate_id = _created(db_client.post("/mandates", json={
            "reference": "TEST-M-PARCOURS", "status": "active", "signature_date": "2030-01-01",
            "ends_at": "2030-07-01", "is_exclusive": False, "id_hunter": hunter_profile(SEED_HUNTER),
            "id_client": client.id, "id_search_request": request.id,
        }))
        estate_id = _created(db_client.post("/estates", json={**ESTATE, "reference": "TEST-PARCOURS"}))
        _created(db_client.post("/pictures", json={
            "url": "https://exemple.test/sejour.jpg", "id_estate": estate_id, "alt_text": "Séjour lumineux, deux fenêtres",
        }))
        _created(db_client.post("/estate-search-requests", json={
            "id_estate": estate_id, "id_search_request": request.id, "id_hunter": hunter_profile(SEED_HUNTER), "status": "kept",
        }))
        proposal_id = _created(db_client.post("/estate-proposed", json={
            "proposition_status": "proposed", "id_hunter": hunter_profile(SEED_HUNTER),
            "id_estate": estate_id, "id_mandate": mandate_id,
        }))

    # 5. Le particulier, avec son vrai jeton, voit la proposition et se dit intéressé.
    with real_token():
        mine = db_client.get("/estate-proposed", headers=as_client)
        assert mine.status_code == 200, mine.text
        assert [row["id"] for row in mine.json()] == [proposal_id]
        proposal = mine.json()[0]
        decided = db_client.put(
            f"/estate-proposed/{proposal_id}",
            headers=as_client,
            json={**proposal, "client_decision": "interested", "client_decided_at": "2030-01-02T10:00:00Z"},
        )
    assert decided.status_code == 200, decided.text
    assert decided.json()["client_decision"] == "interested"
