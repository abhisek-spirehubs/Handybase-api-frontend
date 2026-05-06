import re
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.base import MongoBaseResponse
from app.models.user import UserRole, UserStatus
from app.schemas.common import SocialLinks


# ── Password strength validator (shared) ──────────────────────────────────────

def validate_password_strength(v: str) -> str:
    """
    Enforces a consistent password policy across all password-setting endpoints.
    Rules: min 8 chars (enforced by Field), 1 uppercase, 1 digit.
    """
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[0-9]", v):
        raise ValueError("Password must contain at least one number")
    return v


# ── Request schemas ───────────────────────────────────────────────────────────

class UserLogin(BaseModel):
    email:    EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"


class SendOTPRequest(BaseModel):
    email: EmailStr


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp:   str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_strength(v)


class ChangePasswordWithOtpRequest(BaseModel):
    email:        EmailStr
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_strength(v)


class FCMTokenRequest(BaseModel):
    """Request body for registering a device FCM push token."""
    token: str


class UpdateProfileRequest(BaseModel):
    """
    Common profile fields — applies to all user types.
    Provider-specific fields (business_name, description,
    services, website_url, social_links) are managed
    via PATCH /providers/update separately.
    """
    fname:         Optional[str]      = None
    lname:         Optional[str]      = None
    phone:         Optional[str]      = None
    date_of_birth: Optional[datetime] = None
    avatar_url:    Optional[str]      = None


class AuthUser(BaseModel):
    id:   str
    role: str


# ── Nested schemas ────────────────────────────────────────────────────────────

# class SocialLinks(BaseModel):
#     """
#     Typed social links — frontend can rely on exact field names.
#     All fields optional; only send what the provider has set.
#     """
#     instagram: Optional[str] = None
#     facebook:  Optional[str] = None
#     twitter:   Optional[str] = None
#     linkedin:  Optional[str] = None
#     youtube:   Optional[str] = None


# ── Data schema ───────────────────────────────────────────────────────────────

class UserDataResponse(MongoBaseResponse):
    """
    Full user data object.
    Never returned naked — always wrapped inside APIResponse[UserDataResponse].
    fcm_token intentionally excluded — write-only, never returned to frontend.
    """
    email:          str
    fname:          Optional[str]      = None
    lname:          Optional[str]      = None
    full_name:      Optional[str]      = None
    phone:          Optional[str]      = None
    date_of_birth:  Optional[datetime] = None
    avatar_url:     Optional[str]      = None
    user_type:      UserRole
    status:         UserStatus
    email_verified: bool
    last_login:     Optional[datetime] = None
    created_at:     Optional[datetime] = None
    updated_at:     Optional[datetime] = None

    # Subscription cache — frontend uses to gate UI features on every page load
    subscription_plan:       Optional[str]      = None
    subscription_expires_at: Optional[datetime] = None

    # Provider-only fields — None for clients, frontend should hide these
    business_name:        Optional[str]        = None
    description:          Optional[str]        = None
    experience_years:     Optional[int]        = None
    address:              Optional[str]        = None
    profile_image:        Optional[str]        = None
    portfolio_images:     List[str]            = Field(default_factory=list)
    documents:            List[str]            = Field(default_factory=list)
    services:             List[str]            = Field(default_factory=list)
    rating:               Optional[float]      = None
    total_reviews:        Optional[int]        = None
    is_provider_approved: Optional[bool]       = None
    website_url:          Optional[str]        = None
    social_links:         Optional[SocialLinks] = None  # typed — no longer bare dict