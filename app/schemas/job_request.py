from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field
from app.schemas.base import MongoBaseResponse
from app.models.job_request import JobApplicationStatus, JobRequestStatus


# ── LOCATION ─────────────────────────

class JobLocationSchema(BaseModel):
    place_id: Optional[str] = None
    place_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address_text: Optional[str] = None


# ── JOB REQUEST ──────────────────────

class JobRequestCreate(BaseModel):
    category_id: str
    title: str = Field(..., max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    budget: Optional[float] = Field(None, gt=0)
    preferred_date: Optional[datetime] = None
    location: Optional[JobLocationSchema] = None

    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str


class JobRequestUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    budget: Optional[float] = None
    preferred_date: Optional[datetime] = None
    location: Optional[JobLocationSchema] = None


class JobRequestDataResponse(MongoBaseResponse):
    client_id: str
    category_id: str
    title: str
    description: Optional[str] = None
    budget: Optional[float] = None
    preferred_date: Optional[datetime] = None

    location: Optional[JobLocationSchema] = None

    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str

    job_status: JobRequestStatus
    assigned_provider_id: Optional[str] = None
    assigned_booking_id: Optional[str] = None
    application_count: int = 0

    created_at: datetime
    updated_at: Optional[datetime] = None


# ── APPLICATION ──────────────────────

class JobApplicationCreate(BaseModel):
    quoted_price: float = Field(..., gt=0)
    note: Optional[str] = None


class JobApplicationDataResponse(MongoBaseResponse):
    job_request_id: str
    provider_id: str
    client_id: str
    quoted_price: float
    note: Optional[str] = None
    application_status: JobApplicationStatus

    created_at: datetime
    updated_at: Optional[datetime] = None


# ── SELECT PROVIDER ──────────────────

class SelectProviderRequest(BaseModel):
    application_id: str
    booking_date: datetime
    idempotency_key: Optional[str] = None