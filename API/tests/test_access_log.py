"""
test_access_log.py — Le log d'accès JSON de l'API (chantier FLX, fiche FLX10).

Un handler en mémoire est posé sur le logger `api.access` le temps d'un
test : on lit les lignes JSON que le middleware écrit (conf/logging.py).
"""

import json
import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from src.app.conf.logging import access_logger, access_record
from src.app.main import app
from src.app.utils.roles import CLIENT, get_principal

from .conftest import TEST_HEADERS, principal_as


class ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())


@pytest.fixture
def access_lines() -> Iterator[list[str]]:
    handler = ListHandler()
    access_logger.addHandler(handler)
    try:
        yield handler.lines
    finally:
        access_logger.removeHandler(handler)


def test_one_json_line_per_request(client: TestClient, access_lines: list[str]):
    client.get("/")
    client.get("/estates/999999999")
    assert len(access_lines) == 2
    first, second = (json.loads(line) for line in access_lines)
    assert first["http"] == {"request": {"method": "GET"}, "response": {"status_code": 200}}
    assert first["url"] == {"path": "/"}
    assert first["event"]["duration"] > 0
    assert second["http"]["response"]["status_code"] == 404


def test_role_of_the_caller_is_logged(access_lines: list[str]):
    # Le vrai get_principal pose le rôle ; ici on passe par son remplaçant de
    # test, qui ne l'appelle pas : le rôle manque, et aucune ligne n'en invente.
    app.dependency_overrides[get_principal] = principal_as(CLIENT)
    try:
        TestClient(app, headers=TEST_HEADERS).get("/estates/999999999")
    finally:
        app.dependency_overrides.pop(get_principal, None)
    assert "user" not in json.loads(access_lines[-1])


def test_access_record_carries_the_role():
    record = access_record("GET", "/estates", 200, 5, "Client")
    assert record["user"] == {"roles": ["Client"]}


def test_no_password_token_or_email_in_the_log(access_lines: list[str]):
    secret = "Sup3r-Secret-Pa55word!"
    email = "personne@example.com"
    TestClient(app, headers=TEST_HEADERS).post(
        "/auth/login", json={"email": email, "password": secret},
        params={"email": email},
    )
    TestClient(app, headers={**TEST_HEADERS, "Authorization": "Bearer jeton.secret.abc"}).get("/auth/me")
    logged = "\n".join(access_lines)
    assert len(access_lines) == 2
    for leak in (secret, email, "jeton.secret.abc", "password", "token", "email"):
        assert leak not in logged, leak
