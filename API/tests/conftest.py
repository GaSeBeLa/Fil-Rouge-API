"""
conftest.py — Fixtures pytest partagées par tous les tests.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
pytest découvre automatiquement ce fichier et rend ses fixtures disponibles
dans tous les test_*.py du dossier, sans import explicite — c'est la
convention pytest pour du code de test partagé.

Pour l'instant, une seule fixture : `client`, un TestClient FastAPI prêt à
l'emploi. test_health.py n'en a pas encore besoin (il crée son propre
TestClient), mais les futurs tests sur /users, /roles, etc. pourront
simplement écrire `def test_xxx(client): ...` pour la récupérer.

`fast_hasher` remplace le hacheur argon2 de security.py par un hacheur
volontairement faible, le temps d'un test : le vrai coûte ~300 ms et 512 Mo
par empreinte, ce qui rendrait la suite lente sans rien prouver de plus.
Le format de l'empreinte (PHC) et la vérification restent ceux d'argon2.

`client` (et `db_client`, tests/integration/conftest.py) se présentent en
`Admin` : `get_principal` est remplacé (fiche API2), pour que les tests
écrits avant les rôles restent verts sans jeton. Un test qui vérifie les
droits utilise `principal_as(<rôle>)` ou retire ce remplacement.

Clé d'API (fiche API3) : `api_test_key`, automatique, remplace les clés
lues au démarrage par une seule clé de test, `TEST_API_KEY` ; `client` et
`db_client` l'envoient d'office (`TEST_HEADERS`).

Pas encore de fixture de base de données de test (session PostgreSQL
isolée, rollback automatique après chaque test) : à ajouter quand les
premiers tests touchant réellement la base seront écrits. Les tests
unitaires actuels n'en ont pas besoin : ils remplacent la base par des
objets factices (unittest.mock).
============================================================================
"""

from collections.abc import Callable, Iterator

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from src.app.main import app
from src.app.models import User
from src.app.utils import api_keys, security
from src.app.utils.roles import ADMIN, Principal, get_principal


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


def principal_as(role: str) -> Callable[[], Principal]:
    """Remplaçant de get_principal : un compte activé du rôle donné, sans base."""
    user = User(id=0, email=f"{role.lower()}@test.local", password="-", is_activated=True, id_role=0)
    return lambda: Principal(user=user, role=role)


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
