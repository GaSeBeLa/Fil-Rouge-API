"""
test_seed_demo.py — Le script de démo (chantier DEM, fiche DEM1).

Les étapes du script tournent sur `db_session` (transaction annulée) :
rien n'est écrit pour de vrai. `main()` n'est appelé que pour ses refus,
avant toute connexion.
"""

import pytest
from argon2 import PasswordHasher
from sqlmodel import Session, select

from src.app.models import Client, Hunter, RealEstateManager, Role, User
from src.app.scripts import seed_demo
from src.app.utils.roles import CLIENT, HUNTER, MANAGER, READER

DEMO_PASSWORD = "mot-de-passe-de-demo"


def _demo_users(session: Session) -> list[User]:
    emails = list(seed_demo.DEMO_EMAILS.values())
    return list(session.exec(select(User).where(User.email.in_(emails))).all())  # pyright: ignore[reportAttributeAccessIssue] -- colonne SQLModel, in_ existe à l'exécution


def test_seed_creates_four_activated_accounts_one_per_role(db_session: Session, fast_hasher: PasswordHasher) -> None:
    assert seed_demo.seed(db_session, DEMO_PASSWORD) is True

    users = _demo_users(db_session)
    assert len(users) == 4
    assert all(user.is_activated for user in users)
    roles = {db_session.get(Role, user.id_role).wording for user in users}  # pyright: ignore[reportOptionalMemberAccess] -- FK NOT NULL
    assert roles == {CLIENT, HUNTER, MANAGER, READER}


def test_seed_creates_profiles_hunter_under_demo_manager(db_session: Session, fast_hasher: PasswordHasher) -> None:
    seed_demo.seed(db_session, DEMO_PASSWORD)
    by_email = {user.email: user for user in _demo_users(db_session)}
    manager_id = by_email[seed_demo.DEMO_EMAILS[MANAGER]].id

    hunter = db_session.exec(select(Hunter).where(Hunter.id_user == by_email[seed_demo.DEMO_EMAILS[HUNTER]].id)).one()
    assert hunter.id_realestatemanager == manager_id
    assert db_session.exec(select(RealEstateManager).where(RealEstateManager.id_user == manager_id)).one()
    assert db_session.exec(select(Client).where(Client.id_user == by_email[seed_demo.DEMO_EMAILS[CLIENT]].id)).one()


def test_second_seed_writes_nothing(db_session: Session, fast_hasher: PasswordHasher) -> None:
    seed_demo.seed(db_session, DEMO_PASSWORD)
    users_before = len(db_session.exec(select(User)).all())

    assert seed_demo.seed(db_session, DEMO_PASSWORD) is False
    assert len(db_session.exec(select(User)).all()) == users_before


def test_main_refuses_the_test_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_PASSWORD", DEMO_PASSWORD)
    monkeypatch.setenv("POSTGRES_DB", "fil_rouge_test")
    with pytest.raises(SystemExit, match="fil_rouge_test"):
        seed_demo.main()


@pytest.mark.parametrize("password", [None, "trop-court"])
def test_main_refuses_missing_or_short_password(monkeypatch: pytest.MonkeyPatch, password: str | None) -> None:
    if password is None:
        monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    else:
        monkeypatch.setenv("DEMO_PASSWORD", password)
    with pytest.raises(SystemExit, match="DEMO_PASSWORD"):
        seed_demo.main()
