from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import Field

from app.models.common import LogBase


class InvoiceStatus(str, Enum):
    PAID    = "paid"
    UNPAID  = "unpaid"
    VOID    = "void"


class InvoiceType(str, Enum):
    NEW_SUBSCRIPTION = "new_subscription"
    UPGRADE          = "upgrade"
    RENEWAL          = "renewal"
    CANCELLATION     = "cancellation"   # record only, amount=0


class Invoice(LogBase):
    """
    Generated for every subscription action that involves money.
    Stored permanently — never deleted, only voided.
    """
    # ── References ───────────────────────────────────────────────
    invoice_number: str                     # HB-2026-000001 — sequential
    user_id: str
    subscription_id: str
    plan_id: str
    plan_name: str                          # denormalized — plan may change later
    plan_type: str                          # denormalized

    # ── Type ─────────────────────────────────────────────────────
    invoice_type: InvoiceType

    # ── Amounts ──────────────────────────────────────────────────
    subtotal: float                         # price before tax
    tax_rate: float = 0.0                   # e.g. 0.10 = 10%
    tax_amount: float = 0.0                 # subtotal * tax_rate
    total: float                            # subtotal + tax_amount
    currency: str = "USD"

    # ── Payment ──────────────────────────────────────────────────
    payment_id: Optional[str] = None        # Stripe payment intent id
    status: InvoiceStatus = InvoiceStatus.PAID

    # ── Dates ────────────────────────────────────────────────────
    issued_at: datetime = Field(default_factory=lambda: __import__('datetime').datetime.utcnow())
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None   # None = never expires (free)

    # ── Billing snapshot — in case user changes name/email later ─
    billing_name: Optional[str] = None
    billing_email: Optional[str] = None

    class Settings:
        name = "invoices"
        indexes = [
            "user_id",
            "subscription_id",
            "invoice_number",
            "status",
            "invoice_type",
            "issued_at",
            # Composite indexes for common queries
            [("user_id", 1), ("issued_at", -1)],  # user's invoices sorted by date
            [("status", 1), ("due_date", 1)],  # overdue invoices
            [("invoice_type", 1), ("issued_at", -1)],  # reports by type
            [("payment_id", 1)],  # payment lookup
        ]