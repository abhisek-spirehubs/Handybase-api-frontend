from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Video Portfolio ───────────────────────────────────────────────────────────

class VideoPortfolioItem(BaseModel):
    """Single video entry returned in provider profile."""
    id:          str
    url:         str
    title:       Optional[str] = None
    description: Optional[str] = None
    uploaded_at: datetime

    class Config:
        from_attributes = True


class VideoPortfolioResponse(BaseModel):
    success: bool = True
    message: str
    data:    List[VideoPortfolioItem] = Field(default_factory=list)


class VideoUploadResponse(BaseModel):
    success: bool = True
    message: str
    data:    VideoPortfolioItem


class VideoDeleteResponse(BaseModel):
    success: bool = True
    message: str

