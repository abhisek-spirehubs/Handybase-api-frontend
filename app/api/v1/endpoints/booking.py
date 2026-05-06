from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status

from app.dependencies.auth import get_current_user
from app.models.user import User, UserRole
from app.schemas.booking import (
    BookingCreate,
    BookingUpdate,
    BookingStatusUpdate,
    BookingDataResponse,
)
from app.services.booking_service import BookingService
from app.dependencies.subscription import require_feature
from app.schemas.common import APIResponse, PaginatedResponse, DeleteResponse
from app.models.booking import BookingStatus


router = APIRouter()

# Status-specific success messages — used so the frontend can show meaningful
# toasts without inspecting booking_status in the response body.
_STATUS_MESSAGES = {
    BookingStatus.CONFIRMED: "Booking confirmed successfully",
    BookingStatus.COMPLETED: "Booking marked as completed",
    BookingStatus.CANCELLED: "Booking cancelled successfully",
}


# ── Create booking ─────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=APIResponse[BookingDataResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_booking(
    data:             BookingCreate,
    response:         Response,
    background_tasks: BackgroundTasks,
    current_user:     User = Depends(require_feature("can_book")),
):
    """
    201 Created  → new booking was created.
    200 OK       → idempotency key matched; original booking returned unchanged.

    Frontend can key on the status code to detect replay vs fresh create
    without inspecting the body.
    """
    booking, was_created = await BookingService.create_booking(
        client_id=str(current_user.id),
        client_type=current_user.user_type,
        data=data,
        background_tasks=background_tasks,
    )

    if not was_created:
        # Idempotency replay — nothing was created, correct 201 → 200
        response.status_code = status.HTTP_200_OK

    return {
        "success": True,
        "message": "Booking placed successfully",
        "data":    BookingDataResponse.model_validate(booking),
    }


# ── List bookings — role aware ─────────────────────────────────────────────────

@router.get(
    "",
    response_model=PaginatedResponse[BookingDataResponse],
    status_code=status.HTTP_200_OK,
)
async def get_bookings(
    page:         int  = Query(1, ge=1),
    limit:        int  = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type == UserRole.CLIENT:
        result = await BookingService.get_client_bookings(
            client_id=str(current_user.id),
            page=page,
            limit=limit,
        )
    elif current_user.user_type == UserRole.PROVIDER:
        result = await BookingService.get_provider_bookings(
            provider_id=str(current_user.id),
            page=page,
            limit=limit,
        )
    else:
        result = await BookingService.get_all_bookings(
            page=page,
            limit=limit,
        )

    return {
        "success": True,
        "message": "Bookings fetched successfully",
        "total":   result["total"],
        "data":    [BookingDataResponse.model_validate(b) for b in result["data"]],
    }


# ── Get single booking ─────────────────────────────────────────────────────────

@router.get(
    "/{booking_id}",
    response_model=APIResponse[BookingDataResponse],
    status_code=status.HTTP_200_OK,
)
async def get_booking(
    booking_id:   str,
    current_user: User = Depends(get_current_user),
):
    booking = await BookingService.get_booking_by_id(
        booking_id=booking_id,
        user_id=str(current_user.id),
    )

    return {
        "success": True,
        "message": "Booking fetched successfully",
        "data":    BookingDataResponse.model_validate(booking),
    }


# ── Update booking ─────────────────────────────────────────────────────────────

@router.put(
    "/{booking_id}",
    response_model=APIResponse[BookingDataResponse],
    status_code=status.HTTP_200_OK,
)
async def update_booking(
    booking_id:   str,
    data:         BookingUpdate,
    current_user: User = Depends(get_current_user),
):
    """
    Only allowed while booking is PENDING.
    Empty body is rejected by BookingUpdate.at_least_one_field validator (422).
    """
    booking = await BookingService.update_booking(
        booking_id=booking_id,
        client_id=str(current_user.id),
        data=data,
    )

    return {
        "success": True,
        "message": "Booking updated successfully",
        "data":    BookingDataResponse.model_validate(booking),
    }


# ── Update booking status ──────────────────────────────────────────────────────

@router.patch(
    "/{booking_id}/status",
    response_model=APIResponse[BookingDataResponse],
    status_code=status.HTTP_200_OK,
)
async def update_booking_status(
    booking_id:       str,
    data:             BookingStatusUpdate,
    background_tasks: BackgroundTasks,
    current_user:     User = Depends(get_current_user),
):
    """
    Permission rules (enforced in service):
      CONFIRMED  → provider only
      COMPLETED  → provider only
      CANCELLED  → client or provider; cancellation_reason required

    Invalid transitions return 409 INVALID_TRANSITION (not generic 400).
    """
    booking = await BookingService.update_booking_status(
        booking_id=booking_id,
        user_id=str(current_user.id),
        user_type=current_user.user_type,
        new_status=data.booking_status,
        background_tasks=background_tasks,
        cancellation_reason=data.cancellation_reason,
    )

    # Status-specific message — frontend shows accurate toast without
    # inspecting booking_status in the body.
    message = _STATUS_MESSAGES.get(data.booking_status, "Booking status updated")

    return {
        "success": True,
        "message": message,
        "data":    BookingDataResponse.model_validate(booking),
    }


# ── Delete booking ─────────────────────────────────────────────────────────────

@router.delete(
    "/{booking_id}",
    response_model=DeleteResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_booking(
    booking_id:   str,
    current_user: User = Depends(get_current_user),
):
    """
    Soft-delete only. Active bookings (PENDING / CONFIRMED) must be cancelled first.

    Response includes:
      id         → frontend removes this ID from its cache / list
      deleted_at → powers "deleted X ago" UI or an undo window
      deleted_by → audit trail
    """
    booking = await BookingService.delete_booking(
        booking_id=booking_id,
        client_id=str(current_user.id),
    )

    return {
        "success":    True,
        "message":    "Booking deleted successfully",
        "id":         booking_id,
        "deleted_at": booking.deleted_at or datetime.now(timezone.utc),
        "deleted_by": str(current_user.id),
    }