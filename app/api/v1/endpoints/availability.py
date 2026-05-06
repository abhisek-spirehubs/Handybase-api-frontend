from datetime import datetime
from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_user
from app.models.user import User, UserRole
from app.schemas.availability import (
    SetWeeklyScheduleRequest,
    BlockDatesRequest,
    UnblockDatesRequest,
    AvailabilityResponse,
    AvailableSlotsResponse,
)
from app.schemas.common import APIResponse
from app.services.availability_service import AvailabilityService
from app.core.exceptions import ForbiddenException

router = APIRouter()


def _require_tier2(user: User) -> None:
    if user.user_type != UserRole.PROVIDER:
        raise ForbiddenException("Only providers can manage availability")
    if not user.is_provider_approved:
        raise ForbiddenException("Your provider account is not approved yet")


# ─────────────────────────────────────────
# GET MY AVAILABILITY
# ─────────────────────────────────────────
@router.get(
    "/me",
    response_model=APIResponse[AvailabilityResponse],
)
async def get_my_availability(
    current_user: User = Depends(get_current_user),
):
    _require_tier2(current_user)

    from app.services.subscription_service import SubscriptionService
    features = await SubscriptionService.get_user_features(
        str(current_user.id), UserRole.PROVIDER
    )
    if not features.can_use_calendar:
        raise ForbiddenException(
            "Calendar management requires Tier 2 or above. Please upgrade."
        )

    data = await AvailabilityService.get_availability(str(current_user.id))

    return APIResponse(
        message="Availability retrieved successfully",
        data=data,
    )


# ─────────────────────────────────────────
# SET WEEKLY SCHEDULE
# ─────────────────────────────────────────
@router.put(
    "/schedule",
    response_model=APIResponse[AvailabilityResponse],
)
async def set_weekly_schedule(
    data: SetWeeklyScheduleRequest,
    current_user: User = Depends(get_current_user),
):
    _require_tier2(current_user)

    from app.services.subscription_service import SubscriptionService
    features = await SubscriptionService.get_user_features(
        str(current_user.id), UserRole.PROVIDER
    )
    if not features.can_use_calendar:
        raise ForbiddenException(
            "Calendar management requires Tier 2 or above. Please upgrade."
        )

    result = await AvailabilityService.set_weekly_schedule(
        provider_id=str(current_user.id),
        data=data,
    )

    return APIResponse(
        message="Weekly schedule updated successfully",
        data=result,
    )


# ─────────────────────────────────────────
# BLOCK DATES
# ─────────────────────────────────────────
@router.post(
    "/block",
    response_model=APIResponse[AvailabilityResponse],
)
async def block_dates(
    data: BlockDatesRequest,
    current_user: User = Depends(get_current_user),
):
    _require_tier2(current_user)

    from app.services.subscription_service import SubscriptionService
    features = await SubscriptionService.get_user_features(
        str(current_user.id), UserRole.PROVIDER
    )
    if not features.can_use_calendar:
        raise ForbiddenException(
            "Calendar management requires Tier 2 or above. Please upgrade."
        )

    result = await AvailabilityService.block_dates(
        provider_id=str(current_user.id),
        data=data,
    )

    return APIResponse(
        message="Dates blocked successfully",
        data=result,
    )


# ─────────────────────────────────────────
# UNBLOCK DATES
# ─────────────────────────────────────────
@router.post(
    "/unblock",
    response_model=APIResponse[AvailabilityResponse],
)
async def unblock_dates(
    data: UnblockDatesRequest,
    current_user: User = Depends(get_current_user),
):
    _require_tier2(current_user)

    from app.services.subscription_service import SubscriptionService
    features = await SubscriptionService.get_user_features(
        str(current_user.id), UserRole.PROVIDER
    )
    if not features.can_use_calendar:
        raise ForbiddenException(
            "Calendar management requires Tier 2 or above. Please upgrade."
        )

    result = await AvailabilityService.unblock_dates(
        provider_id=str(current_user.id),
        data=data,
    )

    return APIResponse(
        message="Dates unblocked successfully",
        data=result,
    )


# ─────────────────────────────────────────
# GET PROVIDER AVAILABILITY (PUBLIC)
# ─────────────────────────────────────────
@router.get(
    "/{provider_id}",
    response_model=APIResponse[AvailabilityResponse],
)
async def get_provider_availability(
    provider_id: str,
    _: User = Depends(get_current_user),
):
    data = await AvailabilityService.get_availability(provider_id)

    return APIResponse(
        message="Availability retrieved successfully",
        data=data,
    )


# ─────────────────────────────────────────
# GET AVAILABLE SLOTS
# ─────────────────────────────────────────
@router.get(
    "/{provider_id}/slots",
    response_model=APIResponse[AvailableSlotsResponse],
)
async def get_available_slots(
    provider_id: str,
    date: datetime = Query(...),
    service_duration: int = Query(..., gt=0),
):
    result = await AvailabilityService.get_available_slots(
        provider_id=provider_id,
        date=date,
        service_duration=service_duration,
    )

    return APIResponse(
        message="Available slots fetched successfully",
        data=result,
    )