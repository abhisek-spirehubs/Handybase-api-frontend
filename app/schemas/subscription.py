from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.models.plan import PlanFeatures
from app.models.subscription import SubscriptionStatus
from app.schemas.base import MongoBaseResponse


# ── Request schemas ───────────────────────────────────────────

class SubscribeRequest(BaseModel):
    plan_id: str
    payment_id: Optional[str] = None
    amount_paid: Optional[float] = None
    currency: str = "USD"


class UpgradeRequest(BaseModel):
    plan_id: str
    payment_id: Optional[str] = None
    amount_paid: Optional[float] = None
    currency: str = "USD"


class RenewRequest(BaseModel):
    payment_id: Optional[str] = None
    amount_paid: Optional[float] = None
    currency: str = "USD"


class CancelSubscriptionRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)


# ── Data schemas ──────────────────────────────────────────────

class SubscriptionDataResponse(MongoBaseResponse):
    user_id: str
    plan_id: str
    plan_type: str
    status: SubscriptionStatus
    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    amount_paid: float
    currency: str
    features_snapshot: PlanFeatures
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MySubscriptionDataResponse(BaseModel):
    plan_type: str
    status: SubscriptionStatus
    expires_at: Optional[datetime] = None
    features: PlanFeatures
    is_active: bool