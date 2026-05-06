from typing import List, Optional
from pydantic import Field
from enum import Enum
from app.models.common import BaseLogWithStatus


class ServiceApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Service(BaseLogWithStatus):
    provider_id: str
    category_id: str

    title: str
    description: Optional[str] = None

    price: float
    duration: int

    images: List[str] = Field(default_factory=list)

    # Location fields
    city: Optional[str] = None
    state: Optional[str] = None

    approval_status: ServiceApprovalStatus = ServiceApprovalStatus.PENDING
    is_active: bool = False
    rejection_reason: Optional[str] = None

    class Settings:
        name = "services"
        indexes = [
            # Single fields
            "provider_id",
            "category_id",
            "city",
            "state",
            "approval_status",
            "is_active",
            "status",
            "created_at",
            # Text search
            [("title", "text"), ("description", "text")],
            # Composite indexes for common query patterns
            [("category_id", 1), ("approval_status", 1), ("is_active", 1)],  # browse by category
            [("provider_id", 1), ("approval_status", 1), ("is_active", 1)], # provider's services
            [("city", 1), ("state", 1), ("approval_status", 1), ("is_active", 1)],  # location-based search
            [("approval_status", 1), ("is_active", 1), ("created_at", -1)],  # admin pending list
            [("price", 1), ("approval_status", 1), ("is_active", 1)],  # price sorting
        ]
