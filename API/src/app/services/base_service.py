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
(payment_service.py ; les 13 tables du Client, fiche DRO5, par les chemins
de client_rows.py ; celles du Hunter, fiche DRO6, par hunter_rows.py ;
celles du Manager, fiche DRO7, par manager_rows.py). Une ligne hors du
crochet est introuvable : 404, en lecture comme en modification, comme une
ligne qui n'existe pas. L'Admin
voit tout : le crochet n'est pas appelé pour lui. Sans `viewer` (contrôle
interne, script, test), rien n'est filtré.

En écriture (fiche DRO5) : le POST passe par create_as, le PUT par
replace_visible. Les deux demandent au crochet `owns` si la ligne, telle
qu'elle sera écrite, reste à ce compte ; sinon ConflictError (409), comme
une référence à une ligne qui n'existe pas. Par défaut, oui. Les tables où
le Client, le Hunter ou le Manager écrit le surchargent : client,
search_request, criteria, mandate, estate_proposed, estate_searchrequest,
visit, sale. Se gardent à part, par des champs permis (403) : le compte
(user_service.py), les fiches du chasseur et du manager (hunter_service.py,
real_estate_manager_service.py ; fields_changed_outside ci-dessous),
l'affectation d'une demande (search_request_service.py) ; et les médias
d'avis (review_media_service.py, ADR-051, 403).
============================================================================
"""

from typing import TYPE_CHECKING, Generic, List, Optional, TypeVar

from sqlalchemy import ColumnElement
from sqlmodel import Session, SQLModel

from ..models import User
from ..utils.exceptions import ConflictError, NotFoundError
from ..repositories.base_repository import BaseRepository

if TYPE_CHECKING:
    # Pour le typage seulement : utils/roles.py importe déjà les services.
    from ..utils.roles import Principal

ModelType = TypeVar("ModelType", bound=SQLModel)

# Hors de toute garde de champ : `id`, que replace() ignore ; `created_at`,
# que replace() recopie du corps pour toute table (limite connue, API/README.md).
UNWRITTEN_FIELDS = ("id", "created_at")


def fields_changed_outside(existing: SQLModel, data: SQLModel, allowed: tuple[str, ...]) -> list[str]:
    """
    Les champs que `data` change hors de `allowed`. Tout le modèle, pas les
    seuls champs envoyés : replace() écrit la ligne entière, un champ omis y
    vaudrait son défaut (relecture DRO6).
    """
    kept = allowed + UNWRITTEN_FIELDS
    return [
        field for field, value in data.model_dump().items() if field not in kept and value != getattr(existing, field)
    ]


class BaseService(Generic[ModelType]):
    def __init__(self, repository: BaseRepository[ModelType], not_found_detail: str):
        self.repository = repository
        self.not_found_detail = not_found_detail

    def visible_rows(self, viewer: "Principal") -> Optional[ColumnElement[bool]]:
        """Le crochet « le sien » : la condition SQL des lignes que `viewer` voit, None pour toutes."""
        return None

    def owns(self, session: Session, item: ModelType, viewer: "Principal") -> bool:
        """Le crochet d'écriture : vrai si `item`, tel qu'il sera écrit, est à `viewer`."""
        return True

    def list_all(self, session: Session, viewer: Optional["Principal"] = None) -> List[ModelType]:
        return self.repository.list_all(session, self._where(viewer))

    def get_by_id(self, session: Session, item_id: int, viewer: Optional["Principal"] = None) -> ModelType:
        item = self.repository.get_by_id(session, item_id, self._where(viewer))
        if item is None:
            raise NotFoundError(self.not_found_detail)
        return item

    def create(self, session: Session, item: ModelType, actor: Optional[User] = None) -> ModelType:
        return self.repository.create(session, item)

    def create_as(self, session: Session, item: ModelType, viewer: "Principal") -> ModelType:
        """Le POST de l'API : une ligne qui ne serait pas à `viewer` lève ConflictError (409)."""
        self._check_owner(session, item, viewer)
        return self.create(session, item, actor=viewer.user)

    def replace(self, session: Session, item_id: int, data: ModelType) -> ModelType:
        existing = self.get_by_id(session, item_id)
        return self.repository.replace(session, existing, data)

    def replace_visible(self, session: Session, item_id: int, data: ModelType, viewer: "Principal") -> ModelType:
        """
        Le PUT de l'API : la ligne d'un autre lève NotFoundError (404) ; une
        ligne qui cesserait d'être à `viewer`, ConflictError (409) ; puis
        replace() et ses règles.
        """
        self.get_by_id(session, item_id, viewer)
        self._check_owner(session, data, viewer)
        return self.replace(session, item_id, data)

    def delete(self, session: Session, item_id: int) -> ModelType:
        existing = self.get_by_id(session, item_id)
        return self.repository.delete(session, existing)

    def _check_owner(self, session: Session, item: ModelType, viewer: "Principal") -> None:
        if viewer.is_admin or self.owns(session, item, viewer):
            return
        raise ConflictError("Écriture refusée : la ligne doit rester à vous (ADR-027, « le sien »).")

    def _where(self, viewer: Optional["Principal"]) -> Optional[ColumnElement[bool]]:
        if viewer is None or viewer.is_admin:
            return None
        return self.visible_rows(viewer)
