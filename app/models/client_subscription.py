from datetime import datetime
from typing import Optional
from pydantic import Field
from app.models.common import LogBase
from app.models.plan import PlanFeatures
from app.models.subscription import SubscriptionStatus


class ClientSubscription(LogBase):
    """
    A client's active subscription to a client plan.
    One active subscription per client at a time.
    features_snapshot — copied from ClientPlan.features at purchase time.
    """
    user_id:   str
    plan_id:   str                              # ClientPlan._id
    plan_type: str                              # "client_free" | "client_paid"

    status: SubscriptionStatus = SubscriptionStatus.PENDING

    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None       # None = never expires (free)

    # Payment
    payment_id:  Optional[str] = None
    amount_paid: float = 0.0
    currency:    str   = "USD"

    # Feature snapshot at time of purchase
    features_snapshot: PlanFeatures = Field(default_factory=PlanFeatures)

    # Cancellation
    auto_renew:          bool = False
    cancelled_at:        Optional[datetime] = None
    cancellation_reason: Optional[str] = None

    class Settings:
        name = "client_subscriptions"
        indexes = [
            "user_id",
            "status",
            "expires_at",
            "plan_type",
            # Composite indexes for common queries
            [("user_id", 1), ("status", 1), ("is_deleted", 1)],  # user's active subscription
            [("status", 1), ("expires_at", 1)],  # cron job: find expiring subscriptions
            [("plan_type", 1), ("is_active", 1)],  # plan statistics
            [("created_at", -1)],  # recent subscriptions
        ]