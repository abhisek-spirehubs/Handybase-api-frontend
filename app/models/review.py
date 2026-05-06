from app.models.common import BaseLogWithStatus
from pydantic import Field
from typing import List, Optional


class Review(BaseLogWithStatus):
    client_id:   str
    provider_id: str
    service_id:  str
    booking_id:  str
    rating:      float           = Field(ge=1, le=5)
    comment:     Optional[str]   = None

    # ── Media uploads ─────────────────────────────────────────────────
    # Stores URLs of uploaded images/videos attached to this review.
    # Max 5 files — enforced at service layer.
    media_urls: List[str] = Field(default_factory=list)

    class Settings:
        name = "reviews"
        indexes = [
            [("booking_id",  1), ("is_deleted", 1)],
            [("provider_id", 1), ("is_deleted", 1), ("created_at", -1)],
            [("client_id",   1), ("is_deleted", 1)],
            # Additional indexes for common queries
            [("provider_id", 1), ("rating", 1), ("is_deleted", 1)],  # rating aggregation
            [("provider_id", 1), ("is_deleted", 1), ("rating", -1)],  # sorted by rating
            [("created_at", -1)],  # recent reviews
        ]