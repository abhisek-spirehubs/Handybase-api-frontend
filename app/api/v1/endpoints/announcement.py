from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from typing import Optional

from app.dependencies.auth import get_current_user
from app.models.user import User, UserRole
from app.schemas.announcement import (
    AnnouncementCreate,
    AnnouncementUpdate,
    AnnouncementResponse,
)
from app.schemas.common import APIResponse, MessageResponse, PaginatedResponse
from app.services.announcement_service import AnnouncementService
from app.core.exceptions import ForbiddenException

router = APIRouter()


# ── List ─────────────────────────────────────────

@router.get(
    "",
    response_model=PaginatedResponse[AnnouncementResponse],
)
async def get_announcements(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    is_admin = current_user.user_type == UserRole.ADMIN

    result = await AnnouncementService.get_all(
        page=page,
        limit=limit,
        include_inactive=is_admin,
    )

    return PaginatedResponse(
        message=result["message"],
        total=result["total"],
        data=result["data"],
    )


# ── Create ─────────────────────────────────────────

@router.post(
    "",
    response_model=APIResponse[AnnouncementResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_announcement(
    data: AnnouncementCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type != UserRole.ADMIN:
        raise ForbiddenException("Only admins can create announcements.")

    announcement = await AnnouncementService.create_announcement(
        data=data,
        admin_id=str(current_user.id),
        background_tasks=background_tasks,
    )

    return APIResponse(
        message="Announcement created and broadcast to all users.",
        data=announcement,
    )


# ── Get single ─────────────────────────────────────

@router.get(
    "/{announcement_id}",
    response_model=APIResponse[AnnouncementResponse],
)
async def get_announcement(
    announcement_id: str,
    current_user: User = Depends(get_current_user),
):
    announcement = await AnnouncementService.get_by_id(announcement_id)

    return APIResponse(
        message="Announcement fetched successfully",
        data=announcement,
    )


# ── Update ─────────────────────────────────────────

@router.put(
    "/{announcement_id}",
    response_model=APIResponse[AnnouncementResponse],
)
async def update_announcement(
    announcement_id: str,
    data: AnnouncementUpdate,
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type != UserRole.ADMIN:
        raise ForbiddenException("Only admins can update announcements.")

    announcement = await AnnouncementService.update(
        announcement_id=announcement_id,
        admin_id=str(current_user.id),
        data=data,
    )

    return APIResponse(
        message="Announcement updated successfully",
        data=announcement,
    )


# ── Delete ─────────────────────────────────────────

@router.delete(
    "/{announcement_id}",
    response_model=MessageResponse,
)
async def delete_announcement(
    announcement_id: str,
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type != UserRole.ADMIN:
        raise ForbiddenException("Only admins can delete announcements.")

    await AnnouncementService.delete(
        announcement_id=announcement_id,
        admin_id=str(current_user.id),
    )

    return MessageResponse(message="Announcement deleted successfully")