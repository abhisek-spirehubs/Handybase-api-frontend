from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from app.schemas.base import MongoBaseResponse
from app.models.support_ticket import TicketCategory, TicketStatus


# ── Request ─────────────────────────

class TicketCreate(BaseModel):
    subject: str = Field(..., min_length=5, max_length=200)
    message: str = Field(..., min_length=10, max_length=3000)
    category: TicketCategory = TicketCategory.GENERAL


class TicketReplySchema(BaseModel):
    message: str = Field(..., min_length=5, max_length=3000)
    admin_note: Optional[str] = Field(None, max_length=500)


# ── Response ────────────────────────

class TicketReplyResponse(BaseModel):
    message: str
    replied_by: str
    created_at: datetime


class TicketDataResponse(MongoBaseResponse):
    user_id: str
    subject: str
    message: str
    category: TicketCategory
    status: TicketStatus

    replies: List[TicketReplyResponse] = Field(default_factory=list)

    admin_note: Optional[str] = None
    closed_at: Optional[datetime] = None

    created_at: datetime
    updated_at: Optional[datetime] = None