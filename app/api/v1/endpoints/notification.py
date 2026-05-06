from fastapi import APIRouter, Depends, Query
from typing import Optional

from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.notification_service import NotificationService
from app.schemas.notification import (
    NotificationResponse,
    UnreadCountResponse,
)
from app.schemas.common import MessageResponse, PaginatedResponse

# ── prefix and tags are defined in router.py — never here ────────────────────
router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[NotificationResponse],
    summary="Get paginated notifications for the current user",
)
async def get_notifications(
    page:     int            = Query(1, ge=1),
    limit:    int            = Query(10, ge=1, le=100),
    is_read:  Optional[bool] = Query(None, description="Filter by read status. Omit for all."),
    current_user: User = Depends(get_current_user),
):
    return await NotificationService.get_notifications(
        user_id=str(current_user.id),
        page=page,
        limit=limit,
        is_read=is_read,
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Get unread notification count",
)
async def unread_count(
    current_user: User = Depends(get_current_user),
):
    return await NotificationService.get_unread_count(
        user_id=str(current_user.id),
    )


@router.patch(
    "/read-all",
    response_model=MessageResponse,
    summary="Mark all notifications as read",
)
async def read_all_notifications(
    current_user: User = Depends(get_current_user),
):
    return await NotificationService.mark_all_as_read(
        user_id=str(current_user.id),
    )


@router.patch(
    "/{notification_id}/read",
    response_model=MessageResponse,
    summary="Mark a single notification as read",
)
async def mark_as_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
):
    return await NotificationService.mark_as_read(
        notification_id=notification_id,
        user_id=str(current_user.id),
    )


@router.delete(
    "/{notification_id}",
    response_model=MessageResponse,
    summary="Soft-delete a single notification",
)
async def delete_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
):
    return await NotificationService.delete_notification(
        notification_id=notification_id,
        user_id=str(current_user.id),
    )


@router.delete(
    "",
    response_model=MessageResponse,
    summary="Clear all notifications for the current user",
)
async def clear_notifications(
    current_user: User = Depends(get_current_user),
):
    return await NotificationService.clear_notifications(
        user_id=str(current_user.id),
    )