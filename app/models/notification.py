from typing import Optional
from app.models.common import BaseLogWithStatus


class Notification(BaseLogWithStatus):
    user_id: str

    title: Optional[str] = None
    sub_title: Optional[str] = None
    note: Optional[str] = None

    type: Optional[str] = None
    path: Optional[str] = None
    image: Optional[str] = None

    is_read: bool = False
    is_admin: bool = False

    class Settings:
        name = "notifications"
        indexes = [
            [("user_id", 1), ("is_deleted", 1), ("created_at", -1)],
            [("user_id", 1), ("is_read", 1), ("is_deleted", 1)],
            "type",
            # Additional indexes for common queries
            [("user_id", 1), ("type", 1), ("created_at", -1)],  # filtered by type
            [("is_read", 1), ("created_at", -1)],                # global unread count (admin)
        ]