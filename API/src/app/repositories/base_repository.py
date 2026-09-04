"""
base_repository.py — CRUD générique, partagé par les 11 repositories.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
C'est l'équivalent, en classe réutilisable, des fonctions list_all/
get_one_or_404/create_one/replace_one/delete_one qui vivaient avant dans
main.py. Elles ne connaissent que SQLModel/SQLAlchemy — jamais FastAPI, ni
HTTPException : en cas de problème, elles lèvent NotFoundError ou
ConflictError (voir exceptions.py), à charge pour la couche routers/ de les
traduire en codes HTTP.

Chaque repository de table hérite de BaseRepository[SonModèle] et n'a rien
à réécrire pour les 5 opérations de base. Il peut ensuite ajouter ses
propres méthodes (ex: UserRepository.get_by_email) sans toucher à cette
classe.
============================================================================
"""

from typing import Generic, List, Optional, Type, TypeVar

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select

from ..utils.exceptions import ConflictError

ModelType = TypeVar("ModelType", bound=SQLModel)

_WRITE_CONFLICT_DETAIL = "Contrainte violée (valeur en double ou référence inexistante)."
_DELETE_CONFLICT_DETAIL = "Suppression impossible : cette ligne est encore référencée ailleurs."


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    def list_all(self, session: Session) -> List[ModelType]:
        return session.exec(select(self.model)).all()

    def get_by_id(self, session: Session, item_id: int) -> Optional[ModelType]:
        return session.get(self.model, item_id)

    def create(self, session: Session, item: ModelType) -> ModelType:
        # id toujours réinitialisé : en base, "id" est GENERATED ALWAYS AS
        # IDENTITY, PostgreSQL refuse une valeur explicite (voir 02_migration.sql).
        item.id = None
        session.add(item)
        self._commit_or_raise(session, _WRITE_CONFLICT_DETAIL)
        session.refresh(item)
        return item

    def replace(self, session: Session, existing: ModelType, data: ModelType) -> ModelType:
        for key, value in data.model_dump(exclude={"id"}).items():
            setattr(existing, key, value)
        session.add(existing)
        self._commit_or_raise(session, _WRITE_CONFLICT_DETAIL)
        session.refresh(existing)
        return existing

    def delete(self, session: Session, existing: ModelType) -> ModelType:
        session.delete(existing)
        self._commit_or_raise(session, _DELETE_CONFLICT_DETAIL)
        return existing

    @staticmethod
    def _commit_or_raise(session: Session, conflict_detail: str) -> None:
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise ConflictError(conflict_detail) from exc
