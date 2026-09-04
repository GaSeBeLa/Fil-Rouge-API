from ..models import Picture
from ..repositories.picture_repository import PictureRepository
from .base_service import BaseService


class PictureService(BaseService[Picture]):
    def __init__(self, repository: PictureRepository):
        super().__init__(repository, not_found_detail="Photo introuvable")
