"""
base_service.py — Logique applicative générique, partagée par les 11
services.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Un service ne parle qu'à SON repository (jamais directement à la Session
SQLModel, jamais à FastAPI). Pour l'instant, sans règle métier
supplémentaire, il se contente de déléguer — mais c'est le point d'entrée
naturel pour en ajouter : une sous-classe comme UserService peut surcharger
create() pour hasher le mot de passe avant d'appeler super().create(), sans
que les routers ni les repositories n'aient à changer.

get_by_id lève NotFoundError si la ligne n'existe pas (au lieu de renvoyer
None) : ça évite à chaque appelant de revérifier, et centralise le message
d'erreur associé à cette table.
============================================================================
"""

from typing import Generic, List, TypeVar

from sqlmodel import Session, SQLModel

from ..utils.exceptions import NotFoundError
from ..repositories.base_repository import BaseRepository

ModelType = TypeVar("ModelType", bound=SQLModel)


class BaseService(Generic[ModelType]):
    def __init__(self, repository: BaseRepository[ModelType], not_found_detail: str):
        self.repository = repository
        self.not_found_detail = not_found_detail

    def list_all(self, session: Session) -> List[ModelType]:
        return self.repository.list_all(session)

    def get_by_id(self, session: Session, item_id: int) -> ModelType:
        item = self.repository.get_by_id(session, item_id)
        if item is None:
            raise NotFoundError(self.not_found_detail)
        return item

    def create(self, session: Session, item: ModelType) -> ModelType:
        return self.repository.create(session, item)

    def replace(self, session: Session, item_id: int, data: ModelType) -> ModelType:
        existing = self.get_by_id(session, item_id)
        return self.repository.replace(session, existing, data)

    def delete(self, session: Session, item_id: int) -> ModelType:
        existing = self.get_by_id(session, item_id)
        return self.repository.delete(session, existing)
