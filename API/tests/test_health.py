"""
test_health.py — Test de fumée : l'API démarre et répond correctement.

Ce test ne touche PAS la base de données (pas besoin de PostgreSQL lancé
pour l'exécuter) : il vérifie seulement que FastAPI construit l'application
sans erreur et que la route de health-check répond. Les routes qui
interrogent réellement la base (ex: /users) doivent être testées à part,
avec une vraie base de test — pas ici.

Lancer (depuis le dossier API2/) :
    pytest
"""

from fastapi.testclient import TestClient

from src.app.main import app

client = TestClient(app)


def test_health_check_returns_ok():
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
