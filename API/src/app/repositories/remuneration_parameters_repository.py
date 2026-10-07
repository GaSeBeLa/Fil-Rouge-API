from ..models import RemunerationParameters
from .base_repository import BaseRepository


class RemunerationParametersRepository(BaseRepository[RemunerationParameters]):
    def __init__(self):
        super().__init__(RemunerationParameters)
