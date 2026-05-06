from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from app.schemas.base import MongoBaseResponse


# ── Request ─────────────────────────────────────────

class ClientReviewCreate(BaseModel):
    booking_id: str

    rating: float = Field(..., ge=1, le=5)
    payment_behavior: Optional[float] = Field(None, ge=1, le=5)
    communication: Optional[float] = Field(None, ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=1000)


class ClientReviewUpdate(BaseModel):
    rating: float = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=1000)


# ── Response ────────────────────────────────────────

class ClientReviewResponse(MongoBaseResponse):
    provider_id: str
    client_id: str
    booking_id: str
    service_id: str

    rating: float
    payment_behavior: Optional[float] = None
    communication: Optional[float] = None
    comment: Optional[str] = None

    created_at: datetime