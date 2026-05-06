from typing import List, Optional
from datetime import datetime, timezone
from enum import Enum
from pydantic import Field, BaseModel
from app.models.common import LogBase


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TicketStatus(str, Enum):
    OPEN   = "OPEN"
    CLOSED = "CLOSED"


class TicketCategory(str, Enum):
    GENERAL   = "GENERAL"
    BILLING   = "BILLING"
    TECHNICAL = "TECHNICAL"
    BOOKING   = "BOOKING"
    ACCOUNT   = "ACCOUNT"
    OTHER     = "OTHER"


class TicketReply(BaseModel):
    """Embedded reply — admin email reply is recorded here for audit trail."""
    message:    str
    replied_by: str                              # admin user id
    created_at: datetime = Field(default_factory=utc_now)


class SupportTicket(LogBase):
    """
    One document per support request.
    Admin responds via email — reply is also stored here for audit trail.
    User can track status via GET /support/my-tickets.
    """
    user_id:  str
    subject:  str
    message:  str
    category: TicketCategory = TicketCategory.GENERAL
    status:   TicketStatus   = TicketStatus.OPEN

    # Admin reply stored for audit — user notified via email + push
    replies: List[TicketReply] = Field(default_factory=list)

    # Optional: admin internal note (not shown to user)
    admin_note: Optional[str] = None

    # Timestamps for status changes
    closed_at: Optional[datetime] = None
    closed_by: Optional[str]      = None   # admin user id

    class Settings:
        name = "support_tickets"
        indexes = [
            [("user_id", 1), ("is_deleted", 1), ("created_at", -1)],
            [("status",  1), ("is_deleted", 1), ("created_at", -1)],
            "category",
        ]