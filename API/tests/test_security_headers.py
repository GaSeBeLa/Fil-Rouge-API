"""
test_security_headers.py — Les en-têtes de sécurité sur chaque réponse (choix SEC-HEAD).

Choix SEC-HEAD, accepté par Gabriel le 2026-11-20 (cours « sécurité des
applications », en-têtes de sécurité). Mesuré avant : la réponse ne portait
que `content-type` et `server: uvicorn`. Sans base de données.

Le `server: uvicorn` est ajouté par uvicorn, pas par l'application : il se
retire au lancement (`--no-server-header`, Dockerfile) et ne se voit pas ici.
"""

import pytest
from fastapi.testclient import TestClient

from src.app.main import app

from .conftest import TEST_HEADERS

client = TestClient(app)

EXPECTED = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "cache-control": "no-store",
    "referrer-policy": "no-referrer",
}


@pytest.mark.parametrize(
    ("label", "call"),
    [
        ("200, route publique", lambda: client.get("/")),
        ("401, sans jeton", lambda: client.get("/estates/1", headers=TEST_HEADERS)),
        ("401, sans clé d'API", lambda: client.get("/estates/1")),
        ("404, route inconnue", lambda: client.get("/n-existe-pas")),
    ],
)
def test_every_response_carries_security_headers(label, call):
    response = call()

    missing = {k: v for k, v in EXPECTED.items() if response.headers.get(k) != v}
    assert missing == {}, f"{label} : en-têtes absents ou faux {missing}"
