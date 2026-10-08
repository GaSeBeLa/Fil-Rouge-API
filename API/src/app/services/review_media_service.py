from ..models import ReviewMedia
from ..repositories.review_media_repository import ReviewMediaRepository
from .base_service import BaseService


class ReviewMediaService(BaseService[ReviewMedia]):
    def __init__(self, repository: ReviewMediaRepository):
        super().__init__(repository, not_found_detail="Média introuvable")
