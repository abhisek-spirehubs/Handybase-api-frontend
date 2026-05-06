from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from app.models.booking import Booking, BookingStatus
from app.models.review import Review
from app.models.provider_analytics import ProviderProfileVisit
from app.schemas.analytics import (
    BookingTrendPoint,
    JobPerformanceSchema,
    ProfileEngagementSchema,
    ProviderDashboardSchema,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _thirty_days_ago() -> datetime:
    return _utc_now() - timedelta(days=30)


# ── Live metric computations ──────────────────────────────────────────────────

async def compute_job_performance(provider_id: str) -> JobPerformanceSchema:
    """
    Queries bookings + reviews collections live.
    All-time totals — no date filter.
    """
    all_bookings = await Booking.find(
        Booking.provider_id == provider_id,
        Booking.is_deleted == False,
    ).to_list()

    total      = len(all_bookings)
    completed  = sum(1 for b in all_bookings if b.booking_status == BookingStatus.COMPLETED)
    cancelled  = sum(1 for b in all_bookings if b.booking_status == BookingStatus.CANCELLED)
    completion_rate = round((completed / total * 100) if total else 0.0, 2)
    total_revenue   = sum(
        b.total_amount for b in all_bookings
        if b.booking_status == BookingStatus.COMPLETED
    )

    reviews = await Review.find(
        Review.provider_id == provider_id,
        Review.is_deleted == False,
    ).to_list()

    total_reviews = len(reviews)
    avg_rating    = (
        round(sum(r.rating for r in reviews) / total_reviews, 2)
        if total_reviews else 0.0
    )

    return JobPerformanceSchema(
        total_jobs=total,
        completed_jobs=completed,
        cancelled_jobs=cancelled,
        completion_rate=completion_rate,
        avg_rating=avg_rating,
        total_reviews=total_reviews,
        total_revenue=round(total_revenue, 2),
    )


async def compute_engagement(provider_id: str) -> ProfileEngagementSchema:
    """
    Queries provider_profile_visits live.
    All-time totals + last-30-day breakdown.
    """
    cutoff = _thirty_days_ago()

    total_profile = await ProviderProfileVisit.find(
        ProviderProfileVisit.provider_id == provider_id,
        ProviderProfileVisit.visit_type == "profile",
        ProviderProfileVisit.is_deleted == False,
    ).count()

    total_service = await ProviderProfileVisit.find(
        ProviderProfileVisit.provider_id == provider_id,
        ProviderProfileVisit.visit_type == "service",
        ProviderProfileVisit.is_deleted == False,
    ).count()

    profile_30d = await ProviderProfileVisit.find(
        ProviderProfileVisit.provider_id == provider_id,
        ProviderProfileVisit.visit_type == "profile",
        ProviderProfileVisit.is_deleted == False,
        ProviderProfileVisit.visited_at >= cutoff,
    ).count()

    service_30d = await ProviderProfileVisit.find(
        ProviderProfileVisit.provider_id == provider_id,
        ProviderProfileVisit.visit_type == "service",
        ProviderProfileVisit.is_deleted == False,
        ProviderProfileVisit.visited_at >= cutoff,
    ).count()

    return ProfileEngagementSchema(
        total_profile_visits=total_profile,
        total_service_views=total_service,
        profile_visits_last_30d=profile_30d,
        service_views_last_30d=service_30d,
    )


async def compute_booking_trends(
    provider_id: str, days: int = 30
) -> List[BookingTrendPoint]:
    """
    Queries bookings collection directly filtered by booking_date.
    booking_date = actual service appointment date (not created_at).
    Groups by date in Python and fills missing days with zeros.
    """
    start_date = date.today() - timedelta(days=days - 1)
    start_dt   = datetime.combine(
        start_date, datetime.min.time()
    ).replace(tzinfo=timezone.utc)

    bookings = await Booking.find(
        Booking.provider_id == provider_id,
        Booking.is_deleted == False,
        Booking.booking_date >= start_dt,
    ).to_list()

    # Group by booking_date (the actual service date)
    grouped: dict[date, list] = defaultdict(list)
    for b in bookings:
        day = b.booking_date.astimezone(timezone.utc).date()
        grouped[day].append(b)

    result: List[BookingTrendPoint] = []
    for i in range(days):
        d            = start_date + timedelta(days=i)
        day_bookings = grouped.get(d, [])
        completed    = [
            b for b in day_bookings
            if b.booking_status == BookingStatus.COMPLETED
        ]
        revenue = sum(b.total_amount for b in completed)

        result.append(BookingTrendPoint(
            trend_date=d,
            bookings_count=len(day_bookings),
            completed_count=len(completed),
            revenue=round(revenue, 2),
        ))

    return result


# ── Public API ────────────────────────────────────────────────────────────────

async def get_provider_dashboard(
    provider_id: str, trend_days: int = 30
) -> ProviderDashboardSchema:
    """
    Assembles the full analytics dashboard — everything fetched live.
    Called by GET /providers/me/analytics/dashboard.
    """
    return ProviderDashboardSchema(
        provider_id=provider_id,
        job_performance=await compute_job_performance(provider_id),
        engagement=await compute_engagement(provider_id),
        booking_trends=await compute_booking_trends(provider_id, days=trend_days),
    )


async def record_profile_visit(
    provider_id: str,
    visit_type: str,
    visitor_user_id: Optional[str] = None,
    service_id: Optional[str] = None,
) -> None:
    """
    Inserts one visit event document.
    Called via background_task in provider and service endpoints automatically.
    """
    visit = ProviderProfileVisit(
        provider_id=provider_id,
        visitor_user_id=visitor_user_id,
        visit_type=visit_type,
        service_id=service_id,
    )
    await visit.insert()