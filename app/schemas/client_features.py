from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from app.schemas.base import MongoBaseResponse
from app.models.quotation import QuotationStatus


# ── PRICE COMPARISON ─────────────────────────────────────────

class ProviderPriceSummary(BaseModel):
    provider_id: str
    provider_name: str
    business_name: Optional[str] = None
    profile_image: Optional[str] = None
    rating: float = 0.0
    total_reviews: int = 0
    has_priority: bool = False

    service_id: str
    service_title: str
    service_price: float
    service_duration: int
    city: Optional[str] = None
    state: Optional[str] = None
    images: List[str] = Field(default_factory=list)


# ── QUOTATION REQUEST ───────────────────────────────────────

class QuotationCreate(BaseModel):
    service_id: str
    message: Optional[str] = Field(None, max_length=1000)
    preferred_date: Optional[datetime] = None

    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str


class QuotationRespond(BaseModel):
    quoted_price: float = Field(..., gt=0)
    provider_note: Optional[str] = Field(None, max_length=1000)


class QuotationDecision(BaseModel):
    accept: bool
    booking_date: Optional[datetime] = None
    idempotency_key: Optional[str] = None


# ── RESPONSE ────────────────────────────────────────────────

class QuotationDataResponse(MongoBaseResponse):
    client_id: str
    provider_id: str
    service_id: str

    message: Optional[str] = None
    preferred_date: Optional[datetime] = None

    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str

    quoted_price: Optional[float] = None
    provider_note: Optional[str] = None
    responded_at: Optional[datetime] = None

    quotation_status: QuotationStatus
    expires_at: Optional[datetime] = None
    booking_id: Optional[str] = None

    created_at: datetime
    updated_at: Optional[datetime] = None