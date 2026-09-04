from ..models import Picture
from .base_repository import BaseRepository


class PictureRepository(BaseRepository[Picture]):
    def __init__(self):
        super().__init__(Picture)
