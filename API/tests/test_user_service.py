"""
test_user_service.py — Tests unitaires de UserService (ADR-016).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
UserService est le seul endroit qui transforme un mot de passe en clair en
empreinte. On vérifie donc ce qui ATTEINT le repository (factice) :
jamais le mot de passe en clair.

On vérifie aussi la mise à jour PARTIELLE : seuls les champs fournis
changent, les autres restent intacts.

La fixture `fast_hasher` (conftest.py) évite les ~300 ms d'argon2 par hash.
============================================================================
"""

from unittest.mock import MagicMock

import pytest
from argon2 import PasswordHasher

from src.app.models import User, UserCreate, UserUpdate
from src.app.repositories.user_repository import UserRepository
from src.app.services.user_service import UserService
from src.app.utils.exceptions import NotFoundError
from src.app.utils.security import verify_password

PLAIN = "un-mot-de-passe-assez-long"
NEW_PLAIN = "un-nouveau-mot-de-passe"


@pytest.fixture
def repository() -> MagicMock:
    repo = MagicMock(spec=UserRepository)
    # Le repository factice renvoie ce qu'on lui donne, comme le vrai.
    repo.create.side_effect = lambda session, user: user
    repo.save.side_effect = lambda session, user: user
    return repo


@pytest.fixture
def service(repository: MagicMock) -> UserService:
    return UserService(repository)


@pytest.fixture
def existing_user() -> User:
    return User(id=1, email="ancien@exemple.fr", password="empreinte-existante", is_activated=True, id_role=2)


def test_create_never_sends_plain_password(service: UserService, repository: MagicMock, fast_hasher: PasswordHasher):
    service.create(MagicMock(), UserCreate(email="a@exemple.fr", password=PLAIN, id_role=1))

    sent: User = repository.create.call_args.args[1]
    assert sent.password != PLAIN
    assert verify_password(sent.password, PLAIN) is True


def test_create_copies_other_fields(service: UserService, repository: MagicMock, fast_hasher: PasswordHasher):
    service.create(MagicMock(), UserCreate(email="a@exemple.fr", password=PLAIN, is_activated=False, id_role=3))

    sent: User = repository.create.call_args.args[1]
    assert (sent.email, sent.is_activated, sent.id_role) == ("a@exemple.fr", False, 3)


def test_replace_changes_only_provided_fields(
    service: UserService, repository: MagicMock, existing_user: User, fast_hasher: PasswordHasher
):
    repository.get_by_id.return_value = existing_user

    result = service.replace(MagicMock(), 1, UserUpdate(email="nouveau@exemple.fr"))

    assert result.email == "nouveau@exemple.fr"
    assert result.password == "empreinte-existante"
    assert result.is_activated is True
    assert result.id_role == 2
    repository.save.assert_called_once()


def test_replace_hashes_new_password(
    service: UserService, repository: MagicMock, existing_user: User, fast_hasher: PasswordHasher
):
    repository.get_by_id.return_value = existing_user

    result = service.replace(MagicMock(), 1, UserUpdate(password=NEW_PLAIN))

    assert result.password != NEW_PLAIN
    assert verify_password(result.password, NEW_PLAIN) is True


def test_replace_does_not_use_full_replace(
    service: UserService, repository: MagicMock, existing_user: User, fast_hasher: PasswordHasher
):
    # replace() du repository écraserait les champs omis : il ne doit pas servir ici.
    repository.get_by_id.return_value = existing_user
    service.replace(MagicMock(), 1, UserUpdate(is_activated=False))
    repository.replace.assert_not_called()


def test_replace_unknown_id_raises_not_found(service: UserService, repository: MagicMock):
    repository.get_by_id.return_value = None
    with pytest.raises(NotFoundError) as exc:
        service.replace(MagicMock(), 999, UserUpdate(email="x@exemple.fr"))
    assert str(exc.value) == "Utilisateur introuvable"
    repository.save.assert_not_called()
