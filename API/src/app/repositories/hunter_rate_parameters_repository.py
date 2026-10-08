from ..models import HunterRateParameters
from .base_repository import BaseRepository


class HunterRateParametersRepository(BaseRepository[HunterRateParameters]):
    def __init__(self):
        super().__init__(HunterRateParameters)
