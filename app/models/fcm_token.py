# app/models/fcm_token.py
from datetime import datetime
from typing import Optional
from beanie import Document
from pydantic import Field

class FCMToken(Document):
    user_id: str = Field(..., index=True)           # Reference to User
    token: str = Field(..., index=True)             # FCM registration token
    device_id: Optional[str] = None                 # Client‑provided device identifier
    platform: Optional[str] = None                  # "android", "ios", "web"
    is_active: bool = Field(default=True)           # Soft delete flag
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "fcm_tokens"                        
        indexes = [
            [("user_id", 1), ("device_id", 1)],     # Unique per user+device
            "token",
            [("user_id", 1), ("is_active", 1)],     # user's active tokens
            [("last_used_at", -1)],                 # recently used tokens
        ]