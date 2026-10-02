"""
test_base_repository.py — Tests unitaires de BaseRepository, sans base.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
La Session SQLModel est remplacée par un MagicMock. On ne teste donc PAS
SQL ni PostgreSQL (ce sera le rôle des tests d'intégration, avec une base
de test isolée) : on teste la logique propre au repository.

- `create` ignore l'id fourni (PostgreSQL le génère : GENERATED ALWAYS).
- `replace` recopie les champs mais jamais l'id.
- une IntegrityError au commit devient rollback + ConflictError, avec le
  message propre à l'écriture ou à la suppression.

`User` sert de modèle concret : instancier une classe SQLModel `table=True`
ne touche pas la base.
============================================================================
"""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from src.app.models import User
from src.app.repositories.base_repository import BaseRepository
from src.app.utils.exceptions import ConflictError

WRITE_DETAIL = "Contrainte violée (valeur en double ou référence inexistante)."
DELETE_DETAIL = "Suppression impossible : cette ligne est encore référencée ailleurs."


@pytest.fixture
def repository() -> BaseRepository[User]:
    return BaseRepository(User)


@pytest.fixture
def session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def failing_session() -> MagicMock:
    s = MagicMock()
    s.commit.side_effect = IntegrityError("INSERT ...", {}, Exception("violation"))
    return s


def make_user(**overrides: object) -> User:
    fields: dict[str, object] = {"email": "a@exemple.fr", "password": "empreinte", "id_role": 1}
    fields.update(overrides)
    return User(**fields)  # pyright: ignore[reportArgumentType] — champs fournis dynamiquement, validés par SQLModel


def test_create_resets_client_supplied_id(repository: BaseRepository[User], session: MagicMock):
    user = make_user(id=42)
    repository.create(session, user)
    assert user.id is None
    session.add.assert_called_once_with(user)
    session.commit.assert_called_once()


def test_replace_copies_fields_but_keeps_id(repository: BaseRepository[User], session: MagicMock):
    existing = make_user(id=1)
    data = make_user(id=99, email="nouveau@exemple.fr", id_role=3)

    result = repository.replace(session, existing, data)

    assert result.id == 1
    assert result.email == "nouveau@exemple.fr"
    assert result.id_role == 3


def test_create_conflict_rolls_back_and_raises(repository: BaseRepository[User], failing_session: MagicMock):
    with pytest.raises(ConflictError) as exc:
        repository.create(failing_session, make_user())
    assert str(exc.value) == WRITE_DETAIL
    failing_session.rollback.assert_called_once()
    failing_session.refresh.assert_not_called()


def test_save_conflict_uses_write_detail(repository: BaseRepository[User], failing_session: MagicMock):
    with pytest.raises(ConflictError) as exc:
        repository.save(failing_session, make_user(id=1))
    assert str(exc.value) == WRITE_DETAIL


def test_delete_conflict_uses_delete_detail(repository: BaseRepository[User], failing_session: MagicMock):
    with pytest.raises(ConflictError) as exc:
        repository.delete(failing_session, make_user(id=1))
    assert str(exc.value) == DELETE_DETAIL
    failing_session.rollback.assert_called_once()
