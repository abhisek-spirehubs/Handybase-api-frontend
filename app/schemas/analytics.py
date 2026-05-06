from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Booking trend point (one per day) ─────────────────────────────────────────

class BookingTrendPoint(BaseModel):
    trend_date: date
    bookings_count: int
    completed_count: int
    revenue: float

    class Config:
        from_attributes = True


# ── Job performance ───────────────────────────────────────────────────────────

class JobPerformanceSchema(BaseModel):
    total_jobs: int = Field(..., description="All bookings ever assigned to this provider")
    completed_jobs: int = Field(..., description="Bookings with booking_status == COMPLETED")
    cancelled_jobs: int = Field(..., description="Bookings with booking_status == CANCELLED")
    completion_rate: float = Field(..., description="Completed / total × 100, rounded to 2dp")
    avg_rating: float = Field(..., description="Mean review rating (1–5 scale)")
    total_reviews: int
    total_revenue: float = Field(..., description="Sum of total_amount for completed bookings")


# ── Profile engagement ────────────────────────────────────────────────────────

class ProfileEngagementSchema(BaseModel):
    total_profile_visits: int = Field(..., description="All-time profile page views")
    total_service_views: int = Field(..., description="All-time service detail page views")
    profile_visits_last_30d: int = Field(..., description="Profile views in the last 30 days")
    service_views_last_30d: int = Field(..., description="Service views in the last 30 days")


# ── Full dashboard (returned by GET /dashboard) ───────────────────────────────

class ProviderDashboardSchema(BaseModel):
    provider_id: str
    job_performance: JobPerformanceSchema
    engagement: ProfileEngagementSchema
    booking_trends: List[BookingTrendPoint] = Field(
        default_factory=list,
        description="Daily booking data for the requested window (default 30 days)",
    )



# ── Record visit request body ─────────────────────────────────────────────────

class RecordVisitRequest(BaseModel):
    visit_type: str = Field(..., pattern="^(profile|service)$")
    service_id: Optional[str] = None