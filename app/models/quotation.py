from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import Field
from app.models.common import BaseLogWithStatus


class QuotationStatus(str, Enum):
    PENDING   = "PENDING"    # client sent request, waiting for provider
    RESPONDED = "RESPONDED"  # provider replied with price
    ACCEPTED  = "ACCEPTED"   # client accepted → ready to convert to booking
    REJECTED  = "REJECTED"   # client rejected provider's quote
    EXPIRED   = "EXPIRED"    # provider didn't respond in time
    CANCELLED = "CANCELLED"  # client cancelled before provider responded


class Quotation(BaseLogWithStatus):
    """
    Quotation request — client asks a provider for a price before booking.
    Lifecycle: PENDING → RESPONDED → ACCEPTED (→ Booking) / REJECTED
    """

    # ── Core references ──────────────────────────────────────────────────
    client_id:   str
    provider_id: str
    service_id:  str

    # ── Client request ───────────────────────────────────────────────────
    message:          Optional[str] = None   # client's job description
    preferred_date:   Optional[datetime] = None
    address_line1:    str
    address_line2:    Optional[str] = None
    city:             str
    state:            str
    postal_code:      str
    country:          str

    # ── Provider response ────────────────────────────────────────────────
    quoted_price:     Optional[float] = None
    provider_note:    Optional[str]   = None
    responded_at:     Optional[datetime] = None

    # ── Status ───────────────────────────────────────────────────────────
    quotation_status: QuotationStatus = QuotationStatus.PENDING
    expires_at:       Optional[datetime] = None   # set when provider responds

    # ── Conversion ───────────────────────────────────────────────────────
    booking_id:       Optional[str] = None   # set when client accepts

    class Settings:
        name = "quotations"
        indexes = [
            [("client_id",   1), ("is_deleted", 1), ("created_at", -1)],
            [("provider_id", 1), ("is_deleted", 1), ("created_at", -1)],
            [("service_id",  1), ("quotation_status", 1)],
            "quotation_status",
            # Additional indexes
            [("quotation_status", 1), ("created_at", -1)],  # pending quotations by date
            [("provider_id", 1), ("quotation_status", 1)],  # provider's pending quotes
            [("client_id", 1), ("quotation_status", 1)],    # client's pending quotes
        ]