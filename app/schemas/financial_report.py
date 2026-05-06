from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Single earning row (one completed booking) ────────────────────────────────

class EarningItem(BaseModel):
    booking_id: str
    service_id: str
    client_id: str
    booking_date: datetime
    completed_at: Optional[datetime] = None
    price: float
    tax: float
    total_amount: float

    class Config:
        from_attributes = True


# ── Period summary ────────────────────────────────────────────────────────────

class FinancialSummarySchema(BaseModel):
    provider_id: str
    period_from: date
    period_to: date

    total_earnings: float = Field(..., description="Sum of total_amount for completed bookings")
    total_jobs_completed: int
    total_tax_collected: float
    avg_earning_per_job: float

    earnings: List[EarningItem] = Field(
        default_factory=list,
        description="Itemised list of completed bookings in the period",
    )


# ── Query params (used by endpoint) ──────────────────────────────────────────

class FinancialReportPeriod:
    WEEK   = "week"    # last 7 days
    MONTH  = "month"   # last 30 days
    QUARTER = "quarter" # last 90 days
    CUSTOM = "custom"  # date_from + date_to required