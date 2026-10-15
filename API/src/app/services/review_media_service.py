"""
review_media_service.py — Un média d'avis, ajouté par l'auteur de la note
(ADR-051, fiche API6).

Chemin retenu pour « l'auteur de la note » : `estate_searchrequest.id_hunter`,
le chasseur qui a écrit CETTE note. `search_request.id_hunter` (le chasseur
de la demande) n'est pas suivi : aucune contrainte ne lie les deux en base,
et c'est l'auteur de la note qui répond de ses médias.

- Note introuvable : ConflictError (409), comme la clé étrangère qu'elle
  devance.
- Un autre compte que l'auteur : ForbiddenError (403).

Le POST est réservé à Hunter par le routeur (`create_roles`,
routes/review_media_router.py).

« Le sien » (ADR-027, annexe § 3 ; fiche DRO5) : un Client voit les médias
de l'avis posé sur ses demandes (P5).

Le Hunter (fiche DRO6) voit les médias de ses notes. Le PUT suit la même
règle que le POST : déplacer un média sur la note d'un autre lève
ForbiddenError (403, ADR-051).
"""

from typing import Optional

from sqlalchemy import ColumnElement
from sqlmodel import Session, col

from ..models import ReviewMedia, User
from ..repositories.estate_search_request_repository import EstateSearchRequestRepository
from ..repositories.review_media_repository import ReviewMediaRepository
from ..utils.exceptions import ConflictError, ForbiddenError
from ..utils.roles import CLIENT, HUNTER, Principal
from .base_service import BaseService
from .client_rows import reviews_of
from .hunter_rows import reviews_by


class ReviewMediaService(BaseService[ReviewMedia]):
    def __init__(self, repository: ReviewMediaRepository, reviews: EstateSearchRequestRepository):
        super().__init__(repository, not_found_detail="Média introuvable")
        self.reviews = reviews

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == CLIENT:
            return col(ReviewMedia.id_estate_searchrequest).in_(reviews_of(viewer.profile_id))
        if viewer.role == HUNTER:
            return col(ReviewMedia.id_estate_searchrequest).in_(reviews_by(viewer.profile_id))
        return None

    def create(self, session: Session, item: ReviewMedia, actor: Optional[User] = None) -> ReviewMedia:
        self._check_author(session, item, actor)
        return super().create(session, item, actor)

    def replace_visible(self, session: Session, item_id: int, data: ReviewMedia, viewer: Principal) -> ReviewMedia:
        self.get_by_id(session, item_id, viewer)  # le média d'un autre : 404 d'abord, rien n'est avoué
        self._check_author(session, data, viewer.user)
        return super().replace_visible(session, item_id, data, viewer)

    def _check_author(self, session: Session, item: ReviewMedia, actor: Optional[User]) -> None:
        review = self.reviews.get_by_id(session, item.id_estate_searchrequest)
        if review is None:
            raise ConflictError("Note d'avis introuvable (id_estate_searchrequest).")
        if actor is None or actor.id != review.id_hunter:
            raise ForbiddenError("Seul le chasseur qui a écrit la note y ajoute un média (ADR-051).")
