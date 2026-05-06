from typing import Optional
from datetime import datetime
from pydantic import Field
from app.models.common import BaseLogWithStatus


class ChatRoom(BaseLogWithStatus):
    """
    Chat room for a booking between client and provider
    """
    booking_id: str
    client_id: str
    provider_id: str
    
    # ✅ NEW: Track unread message counts for each participant
    client_unread_count: int = Field(default=0, description="Number of unread messages for client")
    provider_unread_count: int = Field(default=0, description="Number of unread messages for provider")
    
    # ✅ NEW: Last message info (for chat list preview)
    last_message_text: Optional[str] = Field(default=None, description="Last message text")
    last_message_at: Optional[datetime] = Field(default=None, description="Timestamp of last message")
    last_message_sender_id: Optional[str] = Field(default=None, description="Who sent the last message")

    class Settings:
        name = "chat_rooms"
        indexes = [
            [("booking_id", 1), ("is_deleted", 1)],      # lookup by booking — most common
            [("client_id", 1), ("is_deleted", 1)],        # list rooms for client
            [("provider_id", 1), ("is_deleted", 1)],      # list rooms for provider
            [("last_message_at", -1)],                    # for sorting chat list
            # Composite for efficient conversation list with unread counts
            [("client_id", 1), ("last_message_at", -1)],
            [("provider_id", 1), ("last_message_at", -1)],
        ]