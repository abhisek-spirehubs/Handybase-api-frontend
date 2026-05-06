from enum import Enum
from typing import List, Optional
from datetime import datetime, timezone

from pydantic import Field, field_serializer, field_validator
from beanie import PydanticObjectId

from app.schemas.base import MongoBaseModel
from app.models.service import ServiceApprovalStatus
from app.schemas.common import StatusEnum


class ServiceApprovalAction(str, Enum):
    APPROVE = "approve"
    REJECT  = "reject"


class ServiceApprovalRequest(MongoBaseModel):
    action: ServiceApprovalAction
    reason: Optional[str] = None

    @field_validator("reason")
    @classmethod
    def reason_required_on_reject(cls, v, info):
        if info.data.get("action") == ServiceApprovalAction.REJECT and not v:
            raise ValueError("Reason is required when rejecting a service")
        return v


class ServiceResponse(MongoBaseModel):
    id: PydanticObjectId = Field(alias="_id")

    provider_id: str
    category_id: str
    title: str
    description: Optional[str] = None
    price: float
    duration: int
    images: List[str] = Field(default_factory=list)

    city: Optional[str] = None
    state: Optional[str] = None

    # ADDED DEFAULTS TO FIX VALIDATION ERRORS
    approval_status: ServiceApprovalStatus = ServiceApprovalStatus.APPROVED
    is_active: bool = True
    rejection_reason: Optional[str] = None
    status: StatusEnum = StatusEnum.ACTIVE

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_serializer("id")
    def serialize_id(self, value, _info) -> str:
        return str(value)


class PublicServiceResponse(MongoBaseModel):
    id: PydanticObjectId = Field(alias="_id")

    provider_id: str
    category_id: str
    title: str
    description: Optional[str] = None
    price: float
    duration: int
    images: List[str] = Field(default_factory=list)

    city: Optional[str] = None
    state: Optional[str] = None

    # ADDED DEFAULTS TO FIX VALIDATION ERRORS
    approval_status: ServiceApprovalStatus = ServiceApprovalStatus.APPROVED
    is_active: bool = True
    status: StatusEnum = StatusEnum.ACTIVE

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_serializer("id")
    def serialize_id(self, value, _info) -> str:
        return str(value)