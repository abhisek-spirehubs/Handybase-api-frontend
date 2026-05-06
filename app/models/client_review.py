from app.models.common import BaseLogWithStatus
from pydantic import Field
from typing import Optional


class ClientReview(BaseLogWithStatus):
    """
    Provider → Client rating.
    Mirror of Review (Client → Provider) but in the opposite direction.
    One review per booking — enforced at DB level via unique index.
    """
    provider_id: str                          # who is giving the rating
    client_id:   str                          # who is being rated
    booking_id:  str                          # the completed job this is about
    service_id:  str

    rating:           float           = Field(ge=1, le=5)
    payment_behavior: Optional[float] = Field(None, ge=1, le=5,
        description="How promptly / cleanly the client paid (1–5)")
    communication:    Optional[float] = Field(None, ge=1, le=5,
        description="How well the client communicated (1–5)")
    comment:          Optional[str]   = None  # internal — not shown publicly

    class Settings:
        name = "client_reviews"
        indexes = [
            # One review per booking
            [("booking_id", 1), ("is_deleted", 1)],
            # Provider's reviews they've given
            [("provider_id", 1), ("is_deleted", 1), ("created_at", -1)],
            # A client's received ratings (internal / admin view)
            [("client_id", 1), ("is_deleted", 1), ("created_at", -1)],
            # Additional indexes
            [("provider_id", 1), ("rating", 1)],  # provider rating aggregation
            [("client_id", 1), ("rating", 1)],    # client rating aggregation
        ]