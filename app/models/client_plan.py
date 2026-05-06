from typing import Optional
from pydantic import Field
from app.models.common import LogBase
from app.models.plan import PlanFeatures


class ClientPlan(LogBase):
    """
    Plan template for client accounts only.
    plan_type: client_free | client_paid
    """
    name:          str
    plan_type:     str
    price:         float = 0.0
    duration_days: int   = 30
    currency:      str   = "USD"
    description:   Optional[str] = None
    is_active:     bool  = True
    features:      PlanFeatures = Field(default_factory=PlanFeatures)

    class Settings:
        name = "client_plans"
        indexes = [
            "plan_type",
            "is_active",
            # Composite indexes
            [("plan_type", 1), ("is_active", 1)],  # find active plans by type
            [("price", 1), ("is_active", 1)],  # price comparison
            [("created_at", -1)],  # recent plans
        ]