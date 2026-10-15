"""
estate_search_request_model.py — Table de jonction N:N entre estate et
search_request, qui stocke aussi l'avis du chasseur sur ce bien pour cette
demande. Ses médias (audio/vidéo) sont dans review_media.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field
from .field_descriptions import HUNTER_ACCOUNT


class EstateSearchRequest(SQLModel, table=True):
    __tablename__ = "estate_searchrequest"  # pyright: ignore[reportAssignmentType] -- même motif que les autres modèles SQLModel

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    review_hunter: Optional[str] = None
    id_estate: int = Field(foreign_key="estate.id")
    id_search_request: int = Field(foreign_key="search_request.id")
    id_hunter: int = Field(description=HUNTER_ACCOUNT, foreign_key="hunter.id")
