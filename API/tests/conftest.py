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

Pas encore de fixture de base de données de test (session PostgreSQL
isolée, rollback automatique après chaque test) : à ajouter quand les
premiers tests touchant réellement la base seront écrits. Les tests
unitaires actuels n'en ont pas besoin : ils remplacent la base par des
objets factices (unittest.mock).
============================================================================
"""

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from src.app.main import app
from src.app.utils import security


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def fast_hasher(monkeypatch: pytest.MonkeyPatch) -> PasswordHasher:
    """Hacheur argon2 minimal, remis en place automatiquement après le test."""
    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    monkeypatch.setattr(security, "_hasher", weak)
    return weak
