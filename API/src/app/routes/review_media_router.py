from ..models import ReviewMedia
from ..repositories.estate_search_request_repository import EstateSearchRequestRepository
from ..repositories.review_media_repository import ReviewMediaRepository
from ..services.review_media_service import ReviewMediaService
from ..utils.roles import HUNTER
from .crud_router import build_crud_router

router = build_crud_router(
    service=ReviewMediaService(ReviewMediaRepository(), EstateSearchRequestRepository()),
    prefix="/review-media",
    tag="review_media",
    response_model=ReviewMedia,
    # ADR-051 : seul un chasseur écrit une note, donc y ajoute un média ;
    # le service vérifie qu'il en est l'auteur.
    create_roles=(HUNTER,),
)
