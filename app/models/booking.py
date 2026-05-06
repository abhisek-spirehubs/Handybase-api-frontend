from datetime import datetime
from enum import Enum
from typing import Optional

from app.models.common import BaseLogWithStatus


class BookingStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class PaymentStatus(str, Enum):
    UNPAID = "UNPAID"
    PAID = "PAID"
    REFUNDED = "REFUNDED"


class Booking(BaseLogWithStatus):

    # -----------------------
    # Core References
    # -----------------------
    client_id: str
    provider_id: str
    service_id: str

    # -----------------------
    # Booking Details
    # -----------------------
    booking_date: datetime
    slot_end: datetime              # booking_date + service.duration — stored for overlap queries
    booking_status: BookingStatus = BookingStatus.PENDING
    note: Optional[str] = None
    idempotency_key: Optional[str] = None   # client-generated UUID to prevent duplicate bookings

    # -----------------------
    # Pricing Snapshot
    # -----------------------
    price: float
    gst_rate: float                 # rate snapshotted at booking time (e.g. 0.18)
    tax: float = 0.0
    total_amount: float

    # -----------------------
    # Payment
    # -----------------------
    payment_status: PaymentStatus = PaymentStatus.UNPAID
    payment_id: Optional[str] = None

    # -----------------------
    # Address Snapshot
    # -----------------------
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str

    # -----------------------
    # Cancellation
    # -----------------------
    cancelled_by: Optional[str] = None
    cancellation_reason: Optional[str] = None
    cancelled_at: Optional[datetime] = None

    # -----------------------
    # Confirmation
    # -----------------------
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[datetime] = None

    # -----------------------
    # Completion
    # -----------------------
    completed_at: Optional[datetime] = None

    class Settings:
        name = "bookings"
        indexes = [
            # Compound indexes matching exact query patterns in the service
            [("client_id", 1), ("is_deleted", 1), ("created_at", -1)],
            [("provider_id", 1), ("is_deleted", 1), ("created_at", -1)],
            # Overlap conflict check: service_id + status + date window
            [("service_id", 1), ("booking_status", 1), ("booking_date", 1), ("slot_end", 1)],
            # Idempotency: enforce uniqueness at DB level (sparse = ignore None values)
            [("idempotency_key", 1)],
            # Standalone for filtering / admin queries
            "booking_status",
            "payment_status",
            "booking_date",
            # Additional composite indexes for common queries
            [("booking_status", 1), ("booking_date", 1)],  # admin dashboard by date
            [("provider_id", 1), ("booking_status", 1), ("booking_date", 1)],  # provider's upcoming bookings
            [("client_id", 1), ("booking_status", 1)],  # client's active bookings
            [("service_id", 1), ("is_deleted", 1)],  # service booking history
        ]