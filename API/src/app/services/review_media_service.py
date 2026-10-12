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
"""

from typing import Optional

from sqlmodel import Session

from ..models import ReviewMedia, User
from ..repositories.estate_search_request_repository import EstateSearchRequestRepository
from ..repositories.review_media_repository import ReviewMediaRepository
from ..utils.exceptions import ConflictError, ForbiddenError
from .base_service import BaseService


class ReviewMediaService(BaseService[ReviewMedia]):
    def __init__(self, repository: ReviewMediaRepository, reviews: EstateSearchRequestRepository):
        super().__init__(repository, not_found_detail="Média introuvable")
        self.reviews = reviews

    def create(self, session: Session, item: ReviewMedia, actor: Optional[User] = None) -> ReviewMedia:
        review = self.reviews.get_by_id(session, item.id_estate_searchrequest)
        if review is None:
            raise ConflictError("Note d'avis introuvable (id_estate_searchrequest).")
        if actor is None or actor.id != review.id_hunter:
            raise ForbiddenError("Seul le chasseur qui a écrit la note y ajoute un média (ADR-051).")
        return super().create(session, item, actor)
