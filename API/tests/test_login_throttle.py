"""
test_login_throttle.py — Frein aux mots de passe essayés en série sur POST /auth/login.

Trouvé par Gabriel le 2026-11-09 : 15 mauvais mots de passe d'affilée
passaient tous, sans blocage. Deux parties :
- LoginThrottle seul, avec une horloge factice (pas d'attente réelle) ;
- la route, sans base : `authenticate` est remplacé, seul le frein est testé.
"""

from collections.abc import Iterator
from typing import Optional

import pytest
from fastapi.testclient import TestClient

from src.app.models import User
from src.app.routes import auth_router
from src.app.utils.login_throttle import LoginThrottle


class FakeClock:
    """Horloge en secondes, avancée à la main par le test."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def throttle(clock: FakeClock) -> LoginThrottle:
    return LoginThrottle(max_failures=3, window=60, lockout=300, clock=clock)


# --- LoginThrottle seul ------------------------------------------------------


def test_not_locked_below_threshold(throttle: LoginThrottle) -> None:
    throttle.record_failure("a")
    throttle.record_failure("a")

    assert throttle.retry_after("a") is None


def test_locked_at_threshold(throttle: LoginThrottle) -> None:
    for _ in range(3):
        throttle.record_failure("a")

    assert throttle.retry_after("a") == 300


def test_lock_is_per_key(throttle: LoginThrottle) -> None:
    for _ in range(3):
        throttle.record_failure("a")

    assert throttle.retry_after("b") is None


def test_lock_ends_after_lockout(throttle: LoginThrottle, clock: FakeClock) -> None:
    for _ in range(3):
        throttle.record_failure("a")

    clock.now += 299
    assert throttle.retry_after("a") == 1
    clock.now += 1
    assert throttle.retry_after("a") is None


def test_old_failures_leave_the_window(throttle: LoginThrottle, clock: FakeClock) -> None:
    throttle.record_failure("a")
    throttle.record_failure("a")
    clock.now += 61  # les deux premiers sortent de la fenêtre de 60 s
    throttle.record_failure("a")

    assert throttle.retry_after("a") is None


def test_reset_forgets_failures(throttle: LoginThrottle) -> None:
    throttle.record_failure("a")
    throttle.record_failure("a")
    throttle.reset("a")
    throttle.record_failure("a")

    assert throttle.retry_after("a") is None


# --- La route ----------------------------------------------------------------

GOOD = "le-bon-mot-de-passe"
USER = User(id=7, email="frein@test.local", password="-", is_activated=True)


@pytest.fixture
def login_client(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """La vraie route, avec un `authenticate` factice : seul GOOD ouvre."""

    def _authenticate(_session: object, email: str, password: str) -> Optional[User]:
        return USER if email == USER.email and password == GOOD else None

    monkeypatch.setattr(auth_router._service, "authenticate", _authenticate)
    yield client


def _login(client: TestClient, email: str, password: str):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_route_blocks_after_five_failures_on_one_email(login_client: TestClient) -> None:
    for _ in range(5):
        assert _login(login_client, USER.email, "faux").status_code == 401

    blocked = _login(login_client, USER.email, GOOD)  # même le bon mot de passe

    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    assert "access_token" not in blocked.json()


def test_route_email_key_ignores_case(login_client: TestClient) -> None:
    for i in range(5):
        _login(login_client, USER.email.upper() if i % 2 else USER.email, "faux")

    assert _login(login_client, USER.email, GOOD).status_code == 429


def test_route_success_resets_the_email_count(login_client: TestClient) -> None:
    for _ in range(4):
        _login(login_client, USER.email, "faux")
    assert _login(login_client, USER.email, GOOD).status_code == 200

    for _ in range(4):
        _login(login_client, USER.email, "faux")

    assert _login(login_client, USER.email, GOOD).status_code == 200


def test_route_blocks_one_ip_trying_many_emails(login_client: TestClient) -> None:
    for i in range(20):
        _login(login_client, f"inconnu{i}@test.local", "faux")

    assert _login(login_client, USER.email, GOOD).status_code == 429
