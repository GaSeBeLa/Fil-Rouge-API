"""
test_create_admin.py — Le script qui crée le premier compte Admin.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
`scripts/create_admin.py` n'avait aucun test (0 % de couverture, mesuré le
2026-10-14). Le script ouvre sa propre session sur la base de dev : ici,
`Session` est remplacé par la session du test (transaction annulée à la
fin), l'email par `input` et le mot de passe par l'entrée standard (mode
sans terminal) ou par `getpass` (mode terminal).

Ce qui est vérifié :
- le compte créé est Admin, activé, et son mot de passe n'est stocké qu'haché ;
- un email déjà pris (aux majuscules près), un mot de passe trop court, deux
  saisies qui diffèrent : refusés, rien d'écrit ;
- un refus de la base (ConflictError) devient un message, pas une trace.
============================================================================
"""

import io
from collections.abc import Iterator
from contextlib import nullcontext
from typing import Any

import pytest
from argon2 import PasswordHasher
from sqlmodel import Session

from src.app.models import User
from src.app.repositories.user_repository import UserRepository
from src.app.scripts import create_admin
from src.app.services.user_service import UserService
from src.app.utils.exceptions import ConflictError

EMAIL = "admin-neuf@example.com"
PASSWORD = "un-mot-de-passe-long"


class _Terminal(io.StringIO):
    """Une entrée standard qui se dit terminal : le script passe par getpass."""

    def isatty(self) -> bool:
        return True


@pytest.fixture
def script_session(db_session: Session, fast_hasher: PasswordHasher, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    """Le script écrit dans la session du test, pas dans la base de dev."""
    monkeypatch.setattr(create_admin, "Session", lambda _engine: nullcontext(db_session))
    yield db_session


def run(monkeypatch: pytest.MonkeyPatch, email: str = EMAIL, stdin: Any = None) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: email)
    monkeypatch.setattr("sys.stdin", stdin if stdin is not None else io.StringIO(PASSWORD + "\n"))
    create_admin.main()


def accounts(session: Session, email: str = EMAIL) -> list[User]:
    found = UserRepository().find_by_email_ignoring_case(session, email)
    return [found] if found is not None else []


def test_creates_an_activated_admin_with_a_hashed_password(script_session: Session, monkeypatch: pytest.MonkeyPatch):
    run(monkeypatch)
    [user] = accounts(script_session)
    assert (user.system_role, user.is_activated) == ("Admin", True)  # chantier PRF
    assert user.password != PASSWORD and user.password.startswith("$argon2")


def test_terminal_mode_asks_twice(script_session: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(create_admin.getpass, "getpass", lambda _prompt: PASSWORD)
    run(monkeypatch, stdin=_Terminal())
    assert len(accounts(script_session)) == 1


def test_two_different_entries_create_nothing(script_session: Session, monkeypatch: pytest.MonkeyPatch):
    answers = iter([PASSWORD, PASSWORD + "x"])
    monkeypatch.setattr(create_admin.getpass, "getpass", lambda _prompt: next(answers))
    with pytest.raises(SystemExit, match="diffèrent"):
        run(monkeypatch, stdin=_Terminal())
    assert accounts(script_session) == []


def test_a_taken_email_is_refused_whatever_the_case(script_session: Session, monkeypatch: pytest.MonkeyPatch):
    run(monkeypatch)
    with pytest.raises(SystemExit, match="déjà un compte"):
        run(monkeypatch, email=EMAIL.upper())
    assert len(accounts(script_session)) == 1


def test_a_short_password_is_refused(script_session: Session, monkeypatch: pytest.MonkeyPatch):
    with pytest.raises(SystemExit, match="Saisie refusée"):
        run(monkeypatch, stdin=io.StringIO("court\n"))
    assert accounts(script_session) == []


def test_a_refusal_of_the_database_becomes_a_message(script_session: Session, monkeypatch: pytest.MonkeyPatch):
    def refuse(_self: UserService, _session: Session, _item: Any) -> User:
        raise ConflictError("uq_user_email_lower")

    monkeypatch.setattr(UserService, "create", refuse)
    with pytest.raises(SystemExit, match="La base refuse le compte"):
        run(monkeypatch)
