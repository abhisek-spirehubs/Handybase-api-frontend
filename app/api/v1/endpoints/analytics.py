from typing import Optional, List

from fastapi import APIRouter, Depends, Query

from app.dependencies.subscription import require_feature
from app.models.user import User, UserRole
from app.schemas.analytics import (
    ProviderDashboardSchema,
    ProfileEngagementSchema,
    BookingTrendPoint,
)
from app.schemas.common import APIResponse
from app.services import analytics_service
from app.core.exceptions import ForbiddenException

router = APIRouter()


# ─────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────
@router.get(
    "/dashboard",
    response_model=APIResponse[ProviderDashboardSchema],
)
async def get_dashboard(
    trend_days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(require_feature("can_view_analytics")),
):
    if current_user.user_type != UserRole.PROVIDER:
        raise ForbiddenException("Only service providers can access analytics.")

    data = await analytics_service.get_provider_dashboard(
        provider_id=str(current_user.id),
        trend_days=trend_days,
    )

    return APIResponse(
        message="Dashboard fetched successfully",
        data=data,
    )


# ─────────────────────────────────────────
# ENGAGEMENT
# ─────────────────────────────────────────
@router.get(
    "/engagement",
    response_model=APIResponse[ProfileEngagementSchema],
)
async def get_engagement(
    current_user: User = Depends(require_feature("can_view_analytics")),
):
    if current_user.user_type != UserRole.PROVIDER:
        raise ForbiddenException("Only service providers can access analytics.")

    data = await analytics_service.compute_engagement(
        provider_id=str(current_user.id)
    )

    return APIResponse(
        message="Engagement metrics fetched successfully",
        data=data,
    )


# ─────────────────────────────────────────
# BOOKING TRENDS
# ─────────────────────────────────────────
@router.get(
    "/booking-trends",
    response_model=APIResponse[List[BookingTrendPoint]],
)
async def get_booking_trends(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(require_feature("can_view_analytics")),
):
    if current_user.user_type != UserRole.PROVIDER:
        raise ForbiddenException("Only service providers can access analytics.")

    data = await analytics_service.compute_booking_trends(
        provider_id=str(current_user.id),
        days=days,
    )

    return APIResponse(
        message="Booking trends fetched successfully",
        data=data,
    )