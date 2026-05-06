from datetime import datetime, timezone
from typing import Optional
from pydantic import Field
from app.models.common import LogBase


class Announcement(LogBase):
    title:     str
    message:   str
    is_active: bool = True

    class Settings:
        name = "announcements"
        indexes = [
            [("is_active", 1), ("is_deleted", 1), ("created_at", -1)],
            # Additional indexes
            [("created_by", 1), ("created_at", -1)],  # admin's announcements
            [("broadcast_at", -1)],  # scheduled broadcasts
        ]