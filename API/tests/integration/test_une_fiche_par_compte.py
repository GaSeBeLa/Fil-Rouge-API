"""
Une fiche au plus par compte, et pas de fiche pour un compte à system_role
(fiche PRF6).

Décision de Seb du 2026-10-15 (chantier PRF) : un compte porte une seule
casquette — une fiche client, hunter OU real_estate_manager, ou bien un
system_role (Admin, Reader). Le trigger check_one_profile_per_user()
(docker/init-v3/01, section 2 bis) la garde ; l'API rend son refus en 409,
en nommant la contrainte one_profile_per_user.

Chaque test part d'un compte neuf (fixture create_user) : son numéro de
fiche diffère de son numéro de compte, rien ne se cache derrière id = id_user.

Mutant : sans les triggers (DROP TRIGGER trg_*_one_profile,
trg_user_system_role dans la base de test), les trois tests de refus
tombent.
"""

from collections.abc import Callable

from fastapi.testclient import TestClient

# L'Admin crée les fiches Manager et Hunter (create_roles) ; la fiche client
# naît de l'inscription, au rôle Client : elle n'entre pas ici.
MANAGER_BODY = {"first_name": "Une", "last_name": "Fiche", "phone_number": "+33612345678"}

HUNTER_BODY = {
    "first_name": "Deux",
    "last_name": "Fiches",
    "phone_number": "+33612345679",
    "hire_date": "2026-01-05",
}


def test_a_second_profile_for_the_same_account_is_refused(
    db_client: TestClient, create_user: Callable[[str], int]
):
    user_id = create_user("prf6.deux-fiches@example.com")

    first = db_client.post("/real-estate-managers", json={**MANAGER_BODY, "id_user": user_id})
    assert first.status_code == 201, first.text
    assert first.json()["role_wording"] == "Manager"
    assert first.json()["id"] != user_id

    second = db_client.post(
        "/hunters", json={**HUNTER_BODY, "id_user": user_id, "id_realestatemanager": first.json()["id"]}
    )
    assert second.status_code == 409, second.text
    assert "one_profile_per_user" in second.text


def test_a_system_role_on_an_account_with_a_profile_is_refused(
    db_client: TestClient, create_user: Callable[[str], int]
):
    user_id = create_user("prf6.fiche-puis-role@example.com")
    created = db_client.post("/real-estate-managers", json={**MANAGER_BODY, "id_user": user_id})
    assert created.status_code == 201, created.text

    response = db_client.put(f"/users/{user_id}", json={"system_role": "Reader"})
    assert response.status_code == 409, response.text
    assert "one_profile_per_user" in response.text


def test_a_profile_on_an_account_with_a_system_role_is_refused(db_client: TestClient):
    created = db_client.post(
        "/users",
        json={
            "email": "prf6.role-puis-fiche@example.com",
            "password": "un-mot-de-passe-assez-long",
            "system_role": "Reader",
        },
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]

    response = db_client.post("/real-estate-managers", json={**MANAGER_BODY, "id_user": user_id})
    assert response.status_code == 409, response.text
    assert "one_profile_per_user" in response.text
