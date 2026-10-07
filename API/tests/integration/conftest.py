"""
conftest.py (integration) — Base de test PostgreSQL isolée.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Les tests de ce dossier parlent à un VRAI PostgreSQL, pour prouver ce que
les tests unitaires ne voient pas : les contraintes de la base (clés
étrangères, CHECK, UNIQUE, NOT NULL) et leur traduction en codes HTTP.

Deux protections, l'une sur l'autre :

1. UNE AUTRE BASE. Les tests visent `fil_rouge_test`, jamais la base de
   développement `fil_rouge_immobilier`. Même serveur, même utilisateur :
   seul le nom de la base change. Elle se crée avec
   `bash docker/create_test_db.sh` (scripts 01 + 02 de init-v3).

2. TOUT EST ANNULÉ. Chaque test s'exécute dans une transaction ouverte ici
   et annulée (rollback) à la fin, quoi qu'il arrive. Les `commit()` du code
   de l'API deviennent des SAVEPOINT à l'intérieur de cette transaction
   (`join_transaction_mode="create_savepoint"`) : l'API se comporte
   normalement, mais rien n'est jamais réellement écrit. Chaque test part
   donc de la même base, dans n'importe quel ordre.

Base de test absente ou `db` arrêté : ces tests sont SAUTÉS (skipped), avec
le message qui dit quoi lancer. Les tests unitaires, eux, tournent toujours.
============================================================================
"""

import os
from collections.abc import Callable, Iterator

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, create_engine

from src.app.conf.database import DATABASE_URL, get_session
from src.app.main import app

TEST_DB = os.getenv("TEST_POSTGRES_DB", "fil_rouge_test")

USER_PASSWORD = "un-mot-de-passe-assez-long"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Marque `integration` chaque test de ce dossier : `-m "not integration"` les écarte."""
    for item in items:
        if "integration" in item.path.parts:
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def test_engine() -> Iterator[Engine]:
    dev_url = make_url(DATABASE_URL)
    url = dev_url.set(database=TEST_DB)
    if url.database == dev_url.database:
        raise RuntimeError(f"Refusé : la base de test ({TEST_DB}) est la base de développement.")

    engine = create_engine(url)
    try:
        with engine.connect():
            pass
    except OperationalError:
        engine.dispose()
        pytest.skip(f"Base de test {TEST_DB} injoignable : lancer `bash docker/create_test_db.sh`.")
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine: Engine) -> Iterator[Session]:
    """Session dans une transaction annulée à la fin du test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def db_client(db_session: Session, fast_hasher: PasswordHasher) -> Iterator[TestClient]:
    """TestClient sur la vraie app, branché sur `db_session` au lieu de la base de dev."""

    def override_get_session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def create_user(db_client: TestClient) -> Callable[[str], int]:
    """Crée un compte via l'API (rôle 1 = Client, posé par 02) et renvoie son id."""

    def _create(email: str) -> int:
        response = db_client.post("/users", json={"email": email, "password": USER_PASSWORD, "id_role": 1})
        assert response.status_code == 201, response.text
        return response.json()["id"]

    return _create
