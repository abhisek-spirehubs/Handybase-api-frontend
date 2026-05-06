from __future__ import annotations

from datetime import datetime
from typing import Optional, Any

from beanie import PydanticObjectId
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import UserRole, UserStatus
from app.schemas.auth import validate_password_strength


# ── Request schemas ───────────────────────────────────────────────────────────

class ClientRegister(BaseModel):
    email:         EmailStr
    password:      str            = Field(..., min_length=8, max_length=128)
    fname:         Optional[str]  = Field(None, max_length=50)
    lname:         Optional[str]  = Field(None, max_length=50)
    phone:         Optional[str]  = Field(None, pattern=r'^\+?[0-9]{10,15}$')
    date_of_birth: Optional[datetime] = None
    avatar_url:    Optional[str]  = None

    @field_validator("fname", "lname")
    @classmethod
    def strip_names(cls, v):
        if v:
            v = v.strip()
            if not v:
                raise ValueError("Name cannot be empty")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if v.strip() != v:
            raise ValueError("Password cannot start or end with whitespace")
        # Shared strength policy — same rules as ChangePasswordRequest in auth
        return validate_password_strength(v)


class ClientStatusUpdate(BaseModel):
    status: str = Field(..., description="active | inactive")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v not in ("active", "inactive"):
            raise ValueError("Status must be 'active' or 'inactive'")
        return v


# ── Data schema ───────────────────────────────────────────────────────────────

class ClientDataResponse(BaseModel):
    """
    Raw client data object.
    Never returned naked — always wrapped inside APIResponse[ClientDataResponse]
    or PaginatedResponse[ClientDataResponse].
    """
    id: Any = Field(alias="_id")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, v):
        return str(v) if v is not None else v

    email:          str
    fname:          Optional[str]      = None
    lname:          Optional[str]      = None
    full_name:      Optional[str]      = None
    phone:          Optional[str]      = None
    avatar_url:     Optional[str]      = None
    user_type:      UserRole
    status:         UserStatus
    email_verified: bool
    date_of_birth:  Optional[datetime] = None
    last_login:     Optional[datetime] = None
    created_at:     Optional[datetime] = None
    updated_at:     Optional[datetime] = None

    # Subscription cache — frontend uses to gate UI features on every page load
    subscription_plan:       Optional[str]      = None
    subscription_expires_at: Optional[datetime] = None