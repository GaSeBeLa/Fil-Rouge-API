"""
test_base_service.py — Tests unitaires de BaseService, socle des 18 services.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Le repository est remplacé par un MagicMock : aucun appel ne part vers la
base. La session n'est jamais utilisée par le service lui-même (il la
transmet au repository), un MagicMock suffit donc aussi.

Ce qu'on prouve : un id inexistant lève NotFoundError avec le message propre
à la table, et AVANT toute écriture ; le reste est délégué tel quel.
============================================================================
"""

from unittest.mock import MagicMock

import pytest

from src.app.repositories.base_repository import BaseRepository
from src.app.services.base_service import BaseService
from src.app.utils.exceptions import NotFoundError

DETAIL = "Chose introuvable"


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
    repository.list_all.assert_called_once_with(session)


def test_get_by_id_returns_item_when_found(service: BaseService, repository: MagicMock, session: MagicMock):
    item = object()
    repository.get_by_id.return_value = item
    assert service.get_by_id(session, 7) is item
    repository.get_by_id.assert_called_once_with(session, 7)


def test_get_by_id_raises_not_found_with_table_detail(service: BaseService, repository: MagicMock, session: MagicMock):
    repository.get_by_id.return_value = None
    with pytest.raises(NotFoundError) as exc:
        service.get_by_id(session, 999)
    assert str(exc.value) == DETAIL


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
