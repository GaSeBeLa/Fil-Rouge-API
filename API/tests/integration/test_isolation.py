"""
test_isolation.py — Preuve que la base de test est bien isolée.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Avant de croire les autres tests d'intégration, on prouve ici trois choses :

- ils visent la base de test, pas la base de développement ;
- celle-ci contient bien les données de référence de 02 (4 rôles) ;
- une écriture faite par l'API pendant un test est INVISIBLE depuis une
  autre connexion : rien ne sort de la transaction annulée à la fin ;
- une erreur 409 n'empêche pas la suite du test (le SAVEPOINT est annulé,
  pas la transaction du test).
============================================================================
"""

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlmodel import Session, select

from src.app.models import Role

from .conftest import TEST_DB

EMAIL = "isolation@exemple.fr"


def test_engine_targets_test_database(test_engine: Engine):
    assert test_engine.url.database == TEST_DB
    assert test_engine.url.database != "fil_rouge_immobilier"


def test_reference_roles_are_present(db_session: Session):
    wordings = {role.wording for role in db_session.exec(select(Role)).all()}
    assert wordings == {"Admin", "Client", "Hunter", "Manager"}


def test_api_writes_are_invisible_to_other_connections(
    create_user: Callable[[str], int], test_engine: Engine
):
    create_user(EMAIL)

    with test_engine.connect() as other:
        count = other.execute(text('SELECT count(*) FROM "user" WHERE email = :e'), {"e": EMAIL}).scalar_one()
    assert count == 0


def test_conflict_does_not_break_the_test_transaction(db_client: TestClient, create_user: Callable[[str], int]):
    create_user(EMAIL)
    duplicate = db_client.post("/users", json={"email": EMAIL, "password": "x" * 12, "id_role": 1})
    assert duplicate.status_code == 409

    # Après le 409, la session sert encore : le compte créé avant est toujours là.
    assert any(u["email"] == EMAIL for u in db_client.get("/users").json())
