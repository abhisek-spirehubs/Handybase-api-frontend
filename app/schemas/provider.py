from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.user import UserStatus
from app.schemas.common import SocialLinks


# ── Enums ─────────────────────────────────────────────────────────────────────

class ProviderApprovalAction(str, Enum):
    APPROVE = "approve"
    REJECT  = "reject"


class ProviderStatusFilter(str, Enum):
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# ── Base ──────────────────────────────────────────────────────────────────────

class ProviderBaseResponse(BaseModel):
    """
    Base for all provider response schemas.
    Converts ObjectId → str at validation time.
    """
    id: Any = Field(alias="_id")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: Any) -> str:
        return str(v) if v is not None else v


# ── Data schemas ──────────────────────────────────────────────────────────────

class PublicProviderResponse(ProviderBaseResponse):
    """
    Safe public-facing provider profile.
    Only approved providers are ever returned via this schema.
    Never returned naked — always wrapped inside APIResponse[PublicProviderResponse]
    or PaginatedResponse[PublicProviderResponse].

    phone and email are None by default.
    They are populated only for paid clients via get_provider_detail.
    """
    fname:            Optional[str]        = None
    lname:            Optional[str]        = None
    full_name:        Optional[str]        = None
    business_name:    Optional[str]        = None
    description:      Optional[str]        = None
    profile_image:    Optional[str]        = None
    portfolio_images: List[str]            = Field(default_factory=list)
    rating:           float                = 0.0
    total_reviews:    int                  = 0
    services:         List[str]            = Field(default_factory=list)
    experience_years: Optional[int]        = None
    website_url:      Optional[str]        = None
    social_links:     Optional[SocialLinks] = None  # typed — not bare dict

    # Paid-client-only fields — None for free clients and unauthenticated users
    phone:            Optional[str]        = None
    email:            Optional[str]        = None


class AdminProviderResponse(ProviderBaseResponse):
    """
    Full provider profile — for admin panel and provider self-view.
    Includes sensitive fields not exposed publicly.
    Never returned naked — always wrapped inside APIResponse[AdminProviderResponse]
    or PaginatedResponse[AdminProviderResponse].
    """
    fname:            Optional[str]        = None
    lname:            Optional[str]        = None
    full_name:        Optional[str]        = None
    business_name:    Optional[str]        = None
    description:      Optional[str]        = None
    profile_image:    Optional[str]        = None
    portfolio_images: List[str]            = Field(default_factory=list)
    rating:           float                = 0.0
    total_reviews:    int                  = 0
    services:         List[str]            = Field(default_factory=list)
    experience_years: Optional[int]        = None
    website_url:      Optional[str]        = None
    social_links:     Optional[SocialLinks] = None

    # Admin/provider-only fields
    email:                     str
    phone:                     Optional[str]      = None
    address:                   Optional[str]      = None
    documents:                 List[str]          = Field(default_factory=list)
    is_provider_approved:      bool               = False
    provider_rejection_reason: Optional[str]      = None
    status:                    UserStatus

    subscription_plan:         Optional[str]      = None
    subscription_expires_at:   Optional[datetime] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ── Request schemas ───────────────────────────────────────────────────────────

class ProviderApprovalRequest(BaseModel):
    action: ProviderApprovalAction
    reason: Optional[str] = None