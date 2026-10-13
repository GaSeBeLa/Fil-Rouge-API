from ..models import ReviewMedia
from ..repositories.estate_search_request_repository import EstateSearchRequestRepository
from ..repositories.review_media_repository import ReviewMediaRepository
from ..services.review_media_service import ReviewMediaService
from ..utils.roles import ADMIN, CLIENT, HUNTER, READER
from .crud_router import build_crud_router

router = build_crud_router(
    service=ReviewMediaService(ReviewMediaRepository(), EstateSearchRequestRepository()),
    prefix="/review-media",
    tag="review_media",
    response_model=ReviewMedia,
    # ADR-027, annexe § 3, comme estate_searchrequest (P5, H7).
    read_roles=(ADMIN, CLIENT, HUNTER, READER),
    write_roles=(HUNTER,),
    # ADR-051 : seul un chasseur écrit une note, donc y ajoute un média ;
    # le service vérifie qu'il en est l'auteur.
    create_roles=(HUNTER,),
)
