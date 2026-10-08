"""
review_media_model.py — Les médias (audio, vidéo) joints à la note d'avis du
chasseur sur un bien (estate_searchrequest). Plusieurs médias par note.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field


class ReviewMedia(SQLModel, table=True):
    __tablename__ = "review_media"  # pyright: ignore[reportAssignmentType] -- même motif que les autres modèles SQLModel

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    media_url: str
    media_type: str = Field(max_length=10)  # CHECK ('audio' / 'video')
    id_estate_searchrequest: int = Field(foreign_key="estate_searchrequest.id")
