"""
picture_model.py — Les photos rattachées à un bien (estate).
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field


class Picture(SQLModel, table=True):
    __tablename__ = "picture"  # pyright: ignore[reportAssignmentType] -- même motif que les autres modèles SQLModel

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    url: Optional[str] = None
    id_estate: int = Field(foreign_key="estate.id")
    # Ce que montre la photo, pour un lecteur d'écran (WCAG 2.2, 1.1.1).
    # 300 caractères au plus : la base en juge (CHECK).
    alt_text: Optional[str] = None
