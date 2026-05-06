from pydantic import EmailStr, Field
from pydantic import BaseModel
from pydantic import field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum
from app.models.common import LogBase


class UserRole(str, Enum):
    ADMIN    = "admin"
    CLIENT   = "client"
    PROVIDER = "provider"


class RoleItem(BaseModel):
    role: UserRole


class UserStatus(str, Enum):
    ACTIVE   = "active"
    INACTIVE = "inactive"


class User(LogBase):
    fname: Optional[str] = None
    lname: Optional[str] = None
    full_name: Optional[str] = None
    email: EmailStr = Field(..., unique=True)
    password: Optional[str] = None
    email_verified: Optional[bool] = False
    phone: Optional[str] = None
    user_type: UserRole = UserRole.CLIENT
    status: UserStatus = UserStatus.ACTIVE
    date_of_birth: Optional[datetime] = None
    avatar_url: Optional[str] = None

    # OTP fields
    otp_code: Optional[str] = None          # stores SHA-256 hash, never plaintext
    otp_expire: Optional[int] = None        # unix timestamp, OTP valid for 5 min
    otp_verified: Optional[bool] = False
    otp_verified_at: Optional[int] = None   # unix timestamp, starts 10-min reset window

    @field_validator("otp_code", mode="before")
    def _coerce_otp_code(cls, v):
        if v is None:
            return v
        try:
            return str(v)
        except Exception:
            return v

    token: Optional[str] = None
    last_login: Optional[datetime] = None

    # Provider-specific fields
    business_name: Optional[str] = None
    description: Optional[str] = None
    experience_years: Optional[int] = None
    address: Optional[str] = None
    profile_image: Optional[str] = None
    portfolio_images: List[str] = Field(default_factory=list)
    documents: List[str] = Field(default_factory=list)
    rating: float = 0.0
    total_reviews: int = 0
    is_provider_approved: bool = False
    provider_rejection_reason: Optional[str] = None

    # Provider social/contact links (Tier 1 brief requirement)
    website_url: Optional[str] = None
    social_links: Optional[dict] = Field(default_factory=dict)
    # stored as: {"instagram": "url", "facebook": "url", "linkedin": "url"}

    # Subscription cache — avoids extra DB lookup on every authenticated request.
    # Source of truth is always the Subscription document — this is a fast read cache.
    # Updated whenever user subscribes, upgrades, or subscription expires.
    subscription_plan: Optional[str] = None            # mirrors PlanType value e.g. "provider_tier1"
    subscription_expires_at: Optional[datetime] = None # None = never expires (free plans)
    portfolio_videos: List[dict] = Field(default_factory=list)


    class Settings:
        name = "users"
        indexes = [
            # Single field indexes
            "email",
            "user_type",
            "status",
            "created_at",
            # Composite indexes for common queries
            ["email", "user_type"],                    # login + role check
            ["user_type", "status", "is_deleted"],    # list users with filters
            ["is_deleted", "status"],                 # soft delete filter
            ["subscription_plan", "is_deleted"],      # plan-based queries
            ["is_provider_approved", "user_type"],    # provider approval list
        ]