"""
test_base_service.py — Tests unitaires de BaseService, socle des services de table.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Le repository est remplacé par un MagicMock : aucun appel ne part vers la
base. La session n'est jamais utilisée par le service lui-même (il la
transmet au repository), un MagicMock suffit donc aussi.

Ce qu'on prouve : un id inexistant lève NotFoundError avec le message propre
à la table, et AVANT toute écriture ; le reste est délégué tel quel. « Le
sien » (fiche DRO4) : la condition du crochet part au repository, sauf pour
l'Admin ; une ligne hors du crochet n'est pas modifiée. En écriture (fiche
DRO5) : une ligne que le crochet `owns` refuse n'est ni créée ni modifiée,
sauf par l'Admin.
============================================================================
"""

from typing import Optional, cast
from unittest.mock import MagicMock

import pytest
from sqlalchemy import ColumnElement

from src.app.repositories.base_repository import BaseRepository
from src.app.services.base_service import BaseService
from src.app.utils.exceptions import ConflictError, NotFoundError
from src.app.utils.roles import ADMIN, CLIENT, HUNTER, Principal

from .conftest import principal_as

DETAIL = "Chose introuvable"
# Une condition SQL factice : le service la transmet sans la lire.
CONDITION = cast("ColumnElement[bool]", object())


class OnlyMine(BaseService):
    """Une table qui filtre « le sien » : son crochet rend CONDITION."""

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        return CONDITION


class NotMine(BaseService):
    """Une table dont le crochet d'écriture refuse tout : la ligne ne serait pas au compte."""

    def owns(self, session: object, item: object, viewer: Principal) -> bool:
        return False


@pytest.fixture
def repository() -> MagicMock:
    return MagicMock(spec=BaseRepository)


@pytest.fixture
def service(repository: MagicMock) -> BaseService:
    return BaseService(repository, not_found_detail=DETAIL)


@pytest.fixture
def session() -> MagicMock:
    return MagicMock()


def test_list_all_delegates_to_repository(service: BaseService, repository: MagicMock, session: MagicMock):
    repository.list_all.return_value = ["a", "b"]
    assert service.list_all(session) == ["a", "b"]
    repository.list_all.assert_called_once_with(session, None)


def test_get_by_id_returns_item_when_found(service: BaseService, repository: MagicMock, session: MagicMock):
    item = object()
    repository.get_by_id.return_value = item
    assert service.get_by_id(session, 7) is item
    repository.get_by_id.assert_called_once_with(session, 7, None)


def test_get_by_id_raises_not_found_with_table_detail(service: BaseService, repository: MagicMock, session: MagicMock):
    repository.get_by_id.return_value = None
    with pytest.raises(NotFoundError) as exc:
        service.get_by_id(session, 999)
    assert str(exc.value) == DETAIL


@pytest.mark.parametrize(("role", "expected"), [(HUNTER, CONDITION), (ADMIN, None)])
def test_hook_condition_goes_to_the_repository_except_for_admin(
    repository: MagicMock, session: MagicMock, role: str, expected: Optional[ColumnElement[bool]]
):
    service = OnlyMine(repository, not_found_detail=DETAIL)
    viewer = principal_as(role)()
    service.list_all(session, viewer)
    service.get_by_id(session, 7, viewer)
    repository.list_all.assert_called_once_with(session, expected)
    repository.get_by_id.assert_called_once_with(session, 7, expected)


def test_replace_visible_refuses_a_hidden_row_before_writing(repository: MagicMock, session: MagicMock):
    # La ligne n'existe que sans filtre : replace_visible doit passer la condition du crochet.
    repository.get_by_id.side_effect = lambda session, item_id, where=None: None if where is CONDITION else object()
    service = OnlyMine(repository, not_found_detail=DETAIL)
    with pytest.raises(NotFoundError):
        service.replace_visible(session, 3, object(), principal_as(HUNTER)())  # pyright: ignore[reportArgumentType] — idem
    repository.replace.assert_not_called()


def test_create_as_refuses_a_row_that_would_not_be_his(repository: MagicMock, session: MagicMock):
    service = NotMine(repository, not_found_detail=DETAIL)
    with pytest.raises(ConflictError):
        service.create_as(session, object(), principal_as(CLIENT)())  # pyright: ignore[reportArgumentType] — idem
    repository.create.assert_not_called()


def test_create_as_lets_the_admin_write_any_row(repository: MagicMock, session: MagicMock):
    item = object()
    service = NotMine(repository, not_found_detail=DETAIL)
    service.create_as(session, item, principal_as(ADMIN)())  # pyright: ignore[reportArgumentType] — idem
    repository.create.assert_called_once_with(session, item)


def test_replace_visible_refuses_a_row_that_would_stop_being_his(repository: MagicMock, session: MagicMock):
    # La ligne est visible ; c'est la nouvelle valeur qui ne serait plus à lui.
    repository.get_by_id.return_value = object()
    service = NotMine(repository, not_found_detail=DETAIL)
    with pytest.raises(ConflictError):
        service.replace_visible(session, 3, object(), principal_as(CLIENT)())  # pyright: ignore[reportArgumentType] — idem
    repository.replace.assert_not_called()


def test_create_delegates_to_repository(service: BaseService, repository: MagicMock, session: MagicMock):
    item, created = object(), object()
    repository.create.return_value = created
    assert service.create(session, item) is created  # pyright: ignore[reportArgumentType] — un objet quelconque suffit, le service ne le lit pas
    repository.create.assert_called_once_with(session, item)


def test_replace_passes_existing_and_data(service: BaseService, repository: MagicMock, session: MagicMock):
    existing, data = object(), object()
    repository.get_by_id.return_value = existing
    service.replace(session, 3, data)  # pyright: ignore[reportArgumentType] — idem
    repository.replace.assert_called_once_with(session, existing, data)


def test_replace_unknown_id_raises_before_writing(service: BaseService, repository: MagicMock, session: MagicMock):
    repository.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        service.replace(session, 999, object())  # pyright: ignore[reportArgumentType] — idem
    repository.replace.assert_not_called()


def test_delete_passes_existing(service: BaseService, repository: MagicMock, session: MagicMock):
    existing = object()
    repository.get_by_id.return_value = existing
    service.delete(session, 3)
    repository.delete.assert_called_once_with(session, existing)


def test_delete_unknown_id_raises_before_deleting(service: BaseService, repository: MagicMock, session: MagicMock):
    repository.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        service.delete(session, 999)
    repository.delete.assert_not_called()
