from ..models import Picture
from ..repositories.picture_repository import PictureRepository
from ..services.picture_service import PictureService
from .crud_router import build_crud_router

router = build_crud_router(
    service=PictureService(PictureRepository()),
    prefix="/pictures",
    tag="picture",
    response_model=Picture,
)
