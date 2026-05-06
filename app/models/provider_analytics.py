from datetime import datetime, date, timezone
from typing import Optional
from pydantic import Field
from app.models.common import LogBase


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProviderProfileVisit(LogBase):
    provider_id: str
    visitor_user_id: Optional[str] = None
    visit_type: str                  # "profile" | "service"
    service_id: Optional[str] = None
    visited_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "provider_profile_visits"
        indexes = [
            [("provider_id", 1), ("visited_at", -1)],
            [("provider_id", 1), ("visit_type", 1), ("visited_at", -1)],
        ]