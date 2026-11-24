"""
conftest.py — Fixtures pytest partagées par tous les tests.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
pytest découvre automatiquement ce fichier et rend ses fixtures disponibles
dans tous les test_*.py du dossier, sans import explicite — c'est la
convention pytest pour du code de test partagé.

`client` est un TestClient FastAPI prêt à l'emploi : un test écrit
`def test_xxx(client): ...` pour le récupérer. test_health.py n'en a pas
besoin (il crée son propre TestClient).

`fast_hasher` remplace le hacheur argon2 de security.py par un hacheur
volontairement faible, le temps d'un test : le vrai coûte ~300 ms et 512 Mo
par empreinte, ce qui rendrait la suite lente sans rien prouver de plus.
Le format de l'empreinte (PHC) et la vérification restent ceux d'argon2.

`client` (et `db_client`, tests/integration/conftest.py) se présentent en
`Admin` : `get_principal` est remplacé (fiche API2), pour que les tests
écrits avant les rôles restent verts sans jeton. Un test qui vérifie les
droits utilise `principal_as(<rôle>)` ou retire ce remplacement ; un test
qui doit agir sous un compte réel du seed (l'auteur d'un bien, fiche API6)
entoure ses requêtes de `with acting_as(<rôle>, <id>):`.

Clé d'API (fiche API3) : `api_test_key`, automatique, remplace les clés
lues au démarrage par une seule clé de test, `TEST_API_KEY` ; `client` et
`db_client` l'envoient d'office (`TEST_HEADERS`).

Les fixtures de base de données de test (session PostgreSQL isolée,
rollback après chaque test : `db_session`, `db_client`) sont dans
tests/integration/conftest.py. Les tests unitaires de ce dossier n'en ont
pas besoin : ils remplacent la base par des objets factices (unittest.mock).
============================================================================
"""

from collections.abc import Callable, Iterator
from typing import Optional
from contextlib import contextmanager

import pytest
from argon2 import PasswordHasher
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlmodel import Session

from src.app.conf.database import get_session
from src.app.main import app
from src.app.models import User
from src.app.utils import api_keys, login_throttle, security
from src.app.utils.roles import ADMIN, Principal, get_principal, is_ai_hunter, profile_id_of


def pytest_configure(config: pytest.Config) -> None:
    # Déclaré ici faute de pytest.ini ; posé par tests/integration/conftest.py.
    config.addinivalue_line("markers", "integration: test qui parle à la base de test PostgreSQL")


TEST_API_KEY = "cle-de-test-" + "0" * 32
TEST_HEADERS = {api_keys.API_KEY_HEADER: TEST_API_KEY}


@pytest.fixture(autouse=True)
def api_test_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """Une seule clé connue pendant le test : celle-ci (programme TEST)."""
    monkeypatch.setattr(api_keys, "_API_KEYS", {"TEST": TEST_API_KEY})
    return TEST_API_KEY


@pytest.fixture(autouse=True)
def fresh_login_throttle() -> Iterator[None]:
    """Compteurs du frein de connexion vides avant et après chaque test."""
    login_throttle.by_email.clear()
    login_throttle.by_ip.clear()
    yield
    login_throttle.by_email.clear()
    login_throttle.by_ip.clear()


def test_user(role: str, user_id: int) -> User:
    return User(id=user_id, email=f"{role.lower()}@test.local", password="-", is_activated=True)


def principal_as(role: str, user_id: int = 0, profile_id: Optional[int] = None) -> Callable[[], Principal]:
    """Remplaçant de get_principal : un compte activé du rôle donné, sans base."""
    user = test_user(role, user_id)
    return lambda: Principal(user=user, role=role, profile_id=profile_id)


def principal_read_as(role: str, user_id: int) -> Callable[..., Principal]:
    """
    Remplaçant de get_principal pour les tests sur base : le compte n'est
    pas relu, le numéro de sa fiche (profile_id) si, par user_id, comme
    dans get_principal (chantier PRF), et le drapeau du chasseur IA aussi
    (ADR-058).
    """
    user = test_user(role, user_id)

    def _principal(session: Session = Depends(get_session)) -> Principal:
        profile_id = profile_id_of(session, user, role)
        return Principal(user=user, role=role, profile_id=profile_id,
                         is_hunter_ai=is_ai_hunter(session, role, profile_id))

    return _principal


@contextmanager
def acting_as(role: str, user_id: int = 0) -> Iterator[None]:
    """
    Le temps du bloc, l'app se présente sous ce compte, puis reprend le
    précédent. Le numéro de sa fiche est lu dans la base de la requête. `user_id` doit exister en base quand la route l'écrit
    (estate.id_author) : 1 et 2 sont des chasseurs, 25 un manager (seed 02).
    """
    previous = app.dependency_overrides.get(get_principal)
    app.dependency_overrides[get_principal] = principal_read_as(role, user_id)
    try:
        yield
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_principal, None)
        else:
            app.dependency_overrides[get_principal] = previous


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_principal] = principal_as(ADMIN)
    try:
        yield TestClient(app, headers=TEST_HEADERS)
    finally:
        app.dependency_overrides.pop(get_principal, None)


@pytest.fixture
def fast_hasher(monkeypatch: pytest.MonkeyPatch) -> PasswordHasher:
    """Hacheur argon2 minimal, remis en place automatiquement après le test."""
    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    monkeypatch.setattr(security, "_hasher", weak)
    return weak
