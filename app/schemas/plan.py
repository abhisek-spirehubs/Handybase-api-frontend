from typing import Optional
from datetime import datetime
from pydantic import Field
from beanie import PydanticObjectId
from app.schemas.base import MongoBaseModel
from app.models.plan import PlanFeatures



# ── Shared ────────────────────────────────────────────────────────────────────

class PlanResponse(MongoBaseModel):
    id:            PydanticObjectId = Field(alias="_id")
    name:          str
    plan_type:     str
    price:         float
    duration_days: int
    currency:      str
    description:   Optional[str] = None
    is_active:     bool
    features:      PlanFeatures
    created_at:    datetime
    updated_at:    datetime


# ── Client plan schemas ───────────────────────────────────────────────────────

class ClientPlanCreate(MongoBaseModel):
    """Admin creates a client plan."""
    name:          str = Field(..., max_length=100)
    plan_type:     str = Field(..., pattern="^(client_free|client_paid)$")
    price:         float = Field(..., ge=0)
    duration_days: int   = Field(..., gt=0)
    currency:      str   = "USD"
    description:   str   = ""
    features:      PlanFeatures


class ClientPlanUpdate(MongoBaseModel):
    """Admin updates a client plan."""
    name:          Optional[str]          = Field(None, max_length=100)
    price:         Optional[float]        = Field(None, ge=0)
    duration_days: Optional[int]          = Field(None, gt=0)
    description:   Optional[str]          = None
    is_active:     Optional[bool]         = None
    features:      Optional[PlanFeatures] = None


# ── Provider plan schemas ─────────────────────────────────────────────────────

class ProviderPlanCreate(MongoBaseModel):
    """Admin creates a provider plan."""
    name:          str = Field(..., max_length=100)
    plan_type:     str = Field(..., pattern="^(provider_tier1|provider_tier2|provider_tier3)$")
    price:         float = Field(..., ge=0)
    duration_days: int   = Field(..., gt=0)
    currency:      str   = "USD"
    description:   str   = ""
    features:      PlanFeatures


class ProviderPlanUpdate(MongoBaseModel):
    """Admin updates a provider plan."""
    name:          Optional[str]          = Field(None, max_length=100)
    price:         Optional[float]        = Field(None, ge=0)
    duration_days: Optional[int]          = Field(None, gt=0)
    description:   Optional[str]          = None
    is_active:     Optional[bool]         = None
    features:      Optional[PlanFeatures] = None