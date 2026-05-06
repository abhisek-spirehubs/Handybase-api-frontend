from typing import Optional
from app.models.common import BaseLogWithStatus


class ChatMessage(BaseLogWithStatus):
    chat_room_id: str
    sender_id: str

    text: Optional[str] = None
    attachment_url: Optional[str] = None
    attachment_type: Optional[str] = None  # "image", "pdf", etc.

    is_read: bool = False

    class Settings:
        name = "chat_messages"
        indexes = [
            [("chat_room_id", 1), ("is_deleted", 1), ("created_at", -1)],          # get_messages
            [("chat_room_id", 1), ("sender_id", 1), ("is_read", 1), ("is_deleted", 1)],  # mark_as_read
            # Additional indexes for common queries
            [("sender_id", 1), ("created_at", -1)],  # user's sent messages
            [("is_read", 1), ("created_at", 1)],      # unread message queries
        ]