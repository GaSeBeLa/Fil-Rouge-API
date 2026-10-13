"""
base_service.py — Logique applicative générique, partagée par les services
de table.

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

`actor` (fiche API6) : le compte connecté, que le routeur passe à create().
Ignoré ici ; un service s'en sert quand la ligne nomme son auteur (estate,
ADR-047) ou quand le droit dépend de la ligne (review_media, ADR-051).
Appelé sans compte (script, test), create() reçoit None.

« Le sien » (ADR-027, point 2 ; fiche DRO4) : le second contrôle, après le
rôle. Le routeur passe le compte connecté (`viewer`) à list_all, get_by_id
et replace_visible. visible_rows, le crochet, rend la condition SQL des
lignes que ce compte voit ; par défaut, toutes. Une table le surcharge
(payment_service.py). Une ligne hors du crochet est introuvable : 404, en
lecture comme en modification, comme une ligne qui n'existe pas. L'Admin
voit tout : le crochet n'est pas appelé pour lui. Sans `viewer` (contrôle
interne, script, test), rien n'est filtré.
============================================================================
"""

from typing import TYPE_CHECKING, Generic, List, Optional, TypeVar

from sqlalchemy import ColumnElement
from sqlmodel import Session, SQLModel

from ..models import User
from ..utils.exceptions import NotFoundError
from ..repositories.base_repository import BaseRepository

if TYPE_CHECKING:
    # Pour le typage seulement : utils/roles.py importe déjà les services.
    from ..utils.roles import Principal

ModelType = TypeVar("ModelType", bound=SQLModel)


class BaseService(Generic[ModelType]):
    def __init__(self, repository: BaseRepository[ModelType], not_found_detail: str):
        self.repository = repository
        self.not_found_detail = not_found_detail

    def visible_rows(self, viewer: "Principal") -> Optional[ColumnElement[bool]]:
        """Le crochet « le sien » : la condition SQL des lignes que `viewer` voit, None pour toutes."""
        return None

    def list_all(self, session: Session, viewer: Optional["Principal"] = None) -> List[ModelType]:
        return self.repository.list_all(session, self._where(viewer))

    def get_by_id(self, session: Session, item_id: int, viewer: Optional["Principal"] = None) -> ModelType:
        item = self.repository.get_by_id(session, item_id, self._where(viewer))
        if item is None:
            raise NotFoundError(self.not_found_detail)
        return item

    def create(self, session: Session, item: ModelType, actor: Optional[User] = None) -> ModelType:
        return self.repository.create(session, item)

    def replace(self, session: Session, item_id: int, data: ModelType) -> ModelType:
        existing = self.get_by_id(session, item_id)
        return self.repository.replace(session, existing, data)

    def replace_visible(self, session: Session, item_id: int, data: ModelType, viewer: "Principal") -> ModelType:
        """Le PUT de l'API : la ligne d'un autre lève NotFoundError (404), puis replace() et ses règles."""
        self.get_by_id(session, item_id, viewer)
        return self.replace(session, item_id, data)

    def delete(self, session: Session, item_id: int) -> ModelType:
        existing = self.get_by_id(session, item_id)
        return self.repository.delete(session, existing)

    def _where(self, viewer: Optional["Principal"]) -> Optional[ColumnElement[bool]]:
        if viewer is None or viewer.is_admin:
            return None
        return self.visible_rows(viewer)
