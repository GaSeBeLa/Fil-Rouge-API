from ..models import ReviewMedia
from .base_repository import BaseRepository


class ReviewMediaRepository(BaseRepository[ReviewMedia]):
    def __init__(self):
        super().__init__(ReviewMedia)
