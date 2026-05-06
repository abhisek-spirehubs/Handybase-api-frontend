from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Path, Query, status

from app.dependencies.auth import get_current_user
from app.models.support_ticket import TicketCategory, TicketStatus
from app.models.user import User, UserRole
from app.schemas.common import APIResponse, PaginatedResponse, MessageResponse
from app.schemas.support_ticket import (
    TicketCreate,
    TicketReplySchema,
    TicketDataResponse,
)
from app.services.support_ticket import SupportService
from app.core.exceptions import ForbiddenException

router = APIRouter()


# ── List tickets ─────────────────────────────────────────

@router.get(
    "/tickets",
    response_model=PaginatedResponse[TicketDataResponse],
)
async def get_tickets(
    status_filter: Optional[TicketStatus] = Query(None, alias="status"),
    category_filter: Optional[TicketCategory] = Query(None, alias="category"),
    page: int = Query(1),
    limit: int = Query(10),
    current_user: User = Depends(get_current_user),
):
    is_admin = current_user.user_type == UserRole.ADMIN

    if is_admin:
        result = await SupportService.get_all_tickets(
            page=page, limit=limit,
            status=status_filter,
            category=category_filter,
        )
    else:
        result = await SupportService.get_my_tickets(
            user_id=str(current_user.id),
            page=page, limit=limit,
            status=status_filter,
        )

    return PaginatedResponse(
        message=result["message"],
        total=result["total"],
        data=result["data"],
    )


# ── Create ─────────────────────────────────────────

@router.post(
    "/tickets",
    response_model=APIResponse[TicketDataResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_ticket(
    data: TicketCreate,
    current_user: User = Depends(get_current_user),
):
    ticket = await SupportService.create_ticket(
        user_id=str(current_user.id),
        data=data,
    )

    return APIResponse(
        message="Support ticket submitted. We will respond via email.",
        data=ticket,
    )


# ── Get single ─────────────────────────────────────

@router.get(
    "/{ticket_id}",
    response_model=APIResponse[TicketDataResponse],
)
async def get_ticket(
    ticket_id: str = Path(...),
    current_user: User = Depends(get_current_user),
):
    ticket = await SupportService.get_ticket(
        ticket_id=ticket_id,
        caller_id=str(current_user.id),
        is_admin=current_user.user_type == UserRole.ADMIN,
    )

    return APIResponse(
        message="Ticket fetched successfully",
        data=ticket,
    )


# ── Reply ─────────────────────────────────────────

@router.post(
    "/{ticket_id}/reply",
    response_model=APIResponse[TicketDataResponse],
)
async def reply_ticket(
    ticket_id: str,
    data: TicketReplySchema,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type != UserRole.ADMIN:
        raise ForbiddenException("Only admins can reply to tickets.")

    ticket = await SupportService.reply_ticket(
        ticket_id=ticket_id,
        admin=current_user,
        data=data,
        background_tasks=background_tasks,
    )

    return APIResponse(
        message="Reply sent successfully",
        data=ticket,
    )


# ── Close ─────────────────────────────────────────

@router.post(
    "/{ticket_id}/close",
    response_model=APIResponse[TicketDataResponse],
)
async def close_ticket(
    ticket_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type != UserRole.ADMIN:
        raise ForbiddenException("Only admins can close tickets.")

    ticket = await SupportService.close_ticket(
        ticket_id=ticket_id,
        admin=current_user,
        background_tasks=background_tasks,
    )

    return APIResponse(
        message="Ticket closed successfully",
        data=ticket,
    )


# ── Reopen ─────────────────────────────────────────

@router.post(
    "/{ticket_id}/reopen",
    response_model=APIResponse[TicketDataResponse],
)
async def reopen_ticket(
    ticket_id: str,
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type != UserRole.ADMIN:
        raise ForbiddenException("Only admins can reopen tickets.")

    ticket = await SupportService.reopen_ticket(
        ticket_id=ticket_id,
        admin=current_user,
    )

    return APIResponse(
        message="Ticket reopened successfully",
        data=ticket,
    )


# ── Delete ─────────────────────────────────────────

@router.delete(
    "/{ticket_id}",
    response_model=MessageResponse,
)
async def delete_ticket(
    ticket_id: str,
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type != UserRole.ADMIN:
        raise ForbiddenException("Only admins can delete tickets.")

    await SupportService.delete_ticket(
        ticket_id=ticket_id,
        admin=current_user,
    )

    return MessageResponse(message="Ticket deleted successfully")