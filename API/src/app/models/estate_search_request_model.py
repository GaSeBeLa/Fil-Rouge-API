"""
estate_search_request_model.py — Table de jonction N:N entre estate et
search_request, qui stocke aussi le média (audio/vidéo) et l'avis du
chasseur sur ce bien pour cette demande.
"""

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class EstateSearchRequest(SQLModel, table=True):
    __tablename__ = "estate_searchrequest"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    review_hunter: Optional[str] = None
    media_url: Optional[str] = None
    media_type: str = Field(max_length=10)  # NOT NULL + CHECK ('audio'/'video')
    id_estate: int = Field(foreign_key="estate.id")
    id_search_request: int = Field(foreign_key="search_request.id")
    id_hunter: int = Field(foreign_key="hunter.id_user")
