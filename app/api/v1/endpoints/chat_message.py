from fastapi import APIRouter, Depends, Query, BackgroundTasks
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.chat_service import ChatService
from app.schemas.chat_message import (
    ConversationResponse,
    MessageResponse,
    SendMessageRequest,
    MessagesListResponse,
    ConversationsListResponse,
    UnreadCountResponse,
    TotalUnreadCountResponse,
)
from app.schemas.common import MessageResponse as CommonMessageResponse

router = APIRouter()


@router.get(
    "/{booking_id}",
    response_model=ConversationResponse,
    summary="Get the chat room for a confirmed booking",
)
async def get_conversation(
    booking_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Returns the chat room for a booking with unread count.
    Chat room is automatically created when the provider confirms the booking.
    Returns 404 if booking is not confirmed yet.
    """
    return await ChatService.get_conversation(
        booking_id=booking_id,
        user_id=str(current_user.id),
    )


@router.post(
    "/{booking_id}/messages",
    response_model=MessageResponse,
    summary="Send a message in a confirmed booking's chat",
)
async def send_message(
    booking_id: str,
    payload: SendMessageRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    payload.validate_content()
    return await ChatService.send_message(
        booking_id=booking_id,
        sender_id=str(current_user.id),
        background_tasks=background_tasks,
        text=payload.text,
        attachment_url=payload.attachment_url,
        attachment_type=payload.attachment_type,
    )


@router.get(
    "/{booking_id}/messages",
    response_model=MessagesListResponse,
    summary="Get paginated messages for a booking's chat",
)
async def get_messages(
    booking_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    return await ChatService.get_messages(
        booking_id=booking_id,
        user_id=str(current_user.id),
        page=page,
        limit=limit,
    )


@router.patch(
    "/{booking_id}/read",
    response_model=CommonMessageResponse,
    summary="Mark all unread messages from the other party as read",
)
async def mark_as_read(
    booking_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    return await ChatService.mark_as_read(
        booking_id=booking_id,
        user_id=str(current_user.id),
        background_tasks=background_tasks,
    )


@router.get(
    "/conversations/list",
    response_model=ConversationsListResponse,
    summary="Get all conversations with unread counts",
)
async def get_all_conversations(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
):
    """
    Get all chat conversations for the current user.
    Returns a list with unread counts and last message preview.
    Sorted by most recent activity.
    """
    return await ChatService.get_all_conversations(
        user_id=str(current_user.id),
        page=page,
        limit=limit
    )


@router.get(
    "/{booking_id}/unread-count",
    response_model=UnreadCountResponse,
    summary="Get unread count for a specific conversation",
)
async def get_unread_count(
    booking_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Get unread message count for a specific conversation.
    Useful for displaying badges on individual chat items.
    """
    result = await ChatService.get_conversation(
        booking_id=booking_id,
        user_id=str(current_user.id)
    )
    return UnreadCountResponse(
        booking_id=booking_id,
        unread_count=result.unread_count if hasattr(result, "unread_count") else result.get("unread_count", 0)
    )


@router.get(
    "/unread-count/total",
    response_model=TotalUnreadCountResponse,
    summary="Get total unread count across all conversations",
)
async def get_total_unread_count(
    current_user: User = Depends(get_current_user),
):
    """
    Get total unread message count across all conversations.
    Perfect for app-level badge counters (e.g., "Messages (5)" in navigation).
    """
    return await ChatService.get_total_unread_count(
        user_id=str(current_user.id)
    )