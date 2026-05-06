from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional, List
from datetime import datetime
from beanie import PydanticObjectId

# --- HTTP Request/Response ---

class SendMessageRequest(BaseModel):
    text: Optional[str] = Field(None, max_length=5000)
    attachment_url: Optional[str] = None
    attachment_type: Optional[str] = None

    @model_validator(mode="after")
    def validate_content(self):
        if not self.text and not self.attachment_url:
            raise ValueError("Message must contain text or an attachment.")
        if self.attachment_url and not self.attachment_type:
            raise ValueError("attachment_type required when attachment_url provided.")
        return self


class MessageResponse(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    chat_room_id: str
    sender_id: str
    text: Optional[str] = None
    attachment_url: Optional[str] = None
    attachment_type: Optional[str] = None
    is_read: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True)


class ConversationResponse(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    booking_id: str
    client_id: str
    provider_id: str
    unread_count: int = 0
    last_message_text: Optional[str] = None
    last_message_at: Optional[datetime] = None
    last_message_sender_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ConversationListItem(BaseModel):
    room_id: str
    booking_id: str
    client_id: str
    provider_id: str
    other_party_id: str
    unread_count: int = 0
    last_message: Optional[dict] = None
    created_at: Optional[str] = None


class MessagesListResponse(BaseModel):
    success: bool = True
    message: str
    total: int
    data: List[MessageResponse]
    unread_count: int = 0


class ConversationsListResponse(BaseModel):
    success: bool = True
    message: str
    total: int
    data: List[ConversationListItem]


class UnreadCountResponse(BaseModel):
    booking_id: str
    unread_count: int


class TotalUnreadCountResponse(BaseModel):
    total_unread_count: int
    conversations_with_unread: int


# --- WebSocket Message Types ---

class WSConnectionEstablished(BaseModel):
    type: str = "connection_established"
    message: str
    booking_id: str
    room_id: str
    user_id: str
    unread_count: int
    participants: dict
    timestamp: str


class WSNewMessage(BaseModel):
    type: str = "new_message"
    id: str
    sender_id: str
    sender_type: str
    text: Optional[str]
    attachment_url: Optional[str]
    attachment_type: Optional[str]
    is_read: bool
    created_at: str
    unread_counts: dict


class WSMessageSent(BaseModel):
    type: str = "message_sent"
    id: str
    status: str
    timestamp: str


class WSReadReceipt(BaseModel):
    type: str = "read_receipt"
    read_by: str
    timestamp: str


class WSMessagesRead(BaseModel):
    type: str = "messages_read"
    success: bool
    unread_count: int
    messages_updated: int
    timestamp: str