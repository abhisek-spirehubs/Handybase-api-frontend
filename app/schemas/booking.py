from pydantic import BaseModel, Field, ConfigDict, field_serializer, field_validator, model_validator
from typing import Optional, List
from datetime import datetime, timezone
from beanie import PydanticObjectId

from app.models.booking import BookingStatus, PaymentStatus
from app.schemas.base import MongoBaseResponse


# ── Request schemas ───────────────────────────────────────────────────────────

class BookingCreate(BaseModel):
    service_id:      str
    booking_date:    datetime
    note:            Optional[str] = None
    idempotency_key: Optional[str] = None

    address_line1: str
    address_line2: Optional[str] = None
    city:          str
    state:         str
    postal_code:   str
    country:       str

    @field_validator("booking_date", mode="before")
    @classmethod
    def must_be_future(cls, v) -> datetime:
        if isinstance(v, str):
            s = v
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            try:
                v = datetime.fromisoformat(s)
            except Exception:
                raise ValueError("booking_date must be a valid ISO datetime string")

        if not isinstance(v, datetime):
            raise ValueError("booking_date must be a datetime")

        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)

        if v <= datetime.now(timezone.utc):
            raise ValueError("booking_date must be in the future")

        return v


class BookingUpdate(BaseModel):
    """Only allowed while booking is PENDING. Locked once CONFIRMED."""
    booking_date:  Optional[datetime] = None
    note:          Optional[str]      = None
    address_line1: Optional[str]      = None
    address_line2: Optional[str]      = None
    city:          Optional[str]      = None
    state:         Optional[str]      = None
    postal_code:   Optional[str]      = None
    country:       Optional[str]      = None

    @field_validator("booking_date", mode="before")
    @classmethod
    def must_be_future(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return v

        if isinstance(v, str):
            s = v
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            try:
                v = datetime.fromisoformat(s)
            except Exception:
                raise ValueError("booking_date must be a valid ISO datetime string")

        if not isinstance(v, datetime):
            raise ValueError("booking_date must be a datetime")

        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)

        if v <= datetime.now(timezone.utc):
            raise ValueError("booking_date must be in the future")

        return v

    @model_validator(mode="after")
    def at_least_one_field(self) -> "BookingUpdate":
        """
        Reject an empty PUT body — avoids silent no-op updates
        that return 200 with nothing changed.
        """
        if not any(
            v is not None
            for v in self.model_dump(exclude_unset=True).values()
        ):
            raise ValueError("At least one field must be provided for update")
        return self


class BookingStatusUpdate(BaseModel):
    booking_status:      BookingStatus
    cancellation_reason: Optional[str] = None


# ── Response schemas ──────────────────────────────────────────────────────────

class BookingDataResponse(MongoBaseResponse):
    """
    Full booking data object.
    Extends MongoBaseResponse — _id → id conversion and ObjectId
    serialization are handled in the base; no duplication here.

    Never returned naked — always wrapped inside:
      APIResponse[BookingDataResponse]          ← single object
      PaginatedResponse[BookingDataResponse]    ← list
    """

    client_id:   str
    provider_id: str
    service_id:  str
    service_name:  Optional[str] = "Unknown Service"
    provider_name: Optional[str] = "Unknown Provider"
    client_name:   Optional[str] = "Unknown Client"
    booking_date:    datetime
    slot_end:        datetime
    booking_status:  BookingStatus
    note:            Optional[str] = None
    idempotency_key: Optional[str] = None

    price:        float
    gst_rate:     float
    tax:          float
    total_amount: float

    payment_status: PaymentStatus
    payment_id:     Optional[str] = None

    address_line1: str
    address_line2: Optional[str] = None
    city:          str
    state:         str
    postal_code:   str
    country:       str

    cancelled_by:        Optional[str]      = None
    cancellation_reason: Optional[str]      = None
    cancelled_at:        Optional[datetime] = None
    confirmed_by:        Optional[str]      = None
    confirmed_at:        Optional[datetime] = None
    completed_at:        Optional[datetime] = None

    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[str]      = None
    updated_by: Optional[str]      = None