from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from app.schemas.base import MongoBaseResponse


# ── Request ─────────────────────────

class AnnouncementCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    message: str = Field(..., min_length=10, max_length=3000)


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    is_active: Optional[bool] = None


# ── Response ────────────────────────

class AnnouncementResponse(MongoBaseResponse):
    title: str
    message: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None