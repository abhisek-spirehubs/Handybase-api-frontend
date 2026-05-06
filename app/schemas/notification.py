from pydantic import BaseModel, Field, ConfigDict, field_serializer
from datetime import datetime
from typing import Optional
from beanie import PydanticObjectId

# Use the app-wide common schemas — never redefine MessageResponse locally
from app.schemas.common import MessageResponse, PaginatedResponse


class NotificationCreate(BaseModel):
    """Used internally by services only — never an API input."""
    user_id: str
    title: str
    note: str
    type: str
    path: Optional[str] = None
    is_admin: bool = False
        # ── Push notification fields ──────────────────────────────────
    fcm_token: Optional[str] = None     # device token — if provided, push is sent
    data: Optional[dict] = None         # extra payload for frontend routing

    model_config = ConfigDict(extra="ignore")


class NotificationResponse(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    user_id: str
    title: Optional[str] = None
    sub_title: Optional[str] = None
    note: Optional[str] = None
    type: Optional[str] = None
    path: Optional[str] = None
    image: Optional[str] = None
    is_read: bool
    is_admin: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    @field_serializer("id")
    def serialize_id(self, value, _info):
        return str(value)


# Reuse the generic PaginatedResponse from common
# Usage: PaginatedResponse[NotificationResponse]


class UnreadCountResponse(BaseModel):
    count: int