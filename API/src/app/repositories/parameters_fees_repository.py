from ..models import ParametersFees
from .base_repository import BaseRepository


class ParametersFeesRepository(BaseRepository[ParametersFees]):
    def __init__(self):
        super().__init__(ParametersFees)
