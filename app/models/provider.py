from typing import List, Optional
from pydantic import Field
from app.models.common import BaseLogWithStatus


class ProviderProfile(BaseLogWithStatus):
    user_id: str

    # Basic identity
    business_name: str
    bio: Optional[str] = None
    profile_image: Optional[str] = None

    # Services offered
    services: List[str] = Field(default_factory=list)

    # Portfolio
    portfolio_images: List[str] = Field(default_factory=list)

    # Reputation
    rating: float = 0.0
    total_reviews: int = 0

    # Approval
    is_approved: bool = False

    class Settings:
        name = "provider_profiles"
        indexes = [
            "user_id",  # unique reference to User
            "is_approved",
            "rating",
            # Composite indexes for common queries
            [("is_approved", 1), ("rating", -1)],  # approved providers sorted by rating
            [("user_id", 1), ("is_deleted", 1)],  # provider's own profile
            [("created_at", -1)],  # recent registrations
        ]
