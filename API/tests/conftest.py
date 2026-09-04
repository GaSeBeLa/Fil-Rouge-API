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

Pas encore de fixture de base de données de test (session PostgreSQL
isolée, rollback automatique après chaque test) : à ajouter quand les
premiers tests touchant réellement la base seront écrits.
============================================================================
"""

import pytest
from fastapi.testclient import TestClient

from src.app.main import app


@pytest.fixture
def client():
    return TestClient(app)
