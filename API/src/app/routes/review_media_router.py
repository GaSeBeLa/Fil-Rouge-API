from ..models import ReviewMedia
from ..repositories.review_media_repository import ReviewMediaRepository
from ..services.review_media_service import ReviewMediaService
from .crud_router import build_crud_router

router = build_crud_router(
    service=ReviewMediaService(ReviewMediaRepository()),
    prefix="/review-media",
    tag="review_media",
    response_model=ReviewMedia,
)
