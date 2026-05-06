from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import PydanticObjectId

from app.schemas.base import MongoBaseModel
from app.models.invoice import InvoiceStatus, InvoiceType


class InvoiceResponse(MongoBaseModel):
    id: PydanticObjectId = Field(alias="_id")
    invoice_number: str
    user_id: str
    subscription_id: str
    plan_name: str
    plan_type: str
    invoice_type: InvoiceType
    subtotal: float
    tax_rate: float
    tax_amount: float
    total: float
    currency: str
    payment_id: Optional[str] = None
    status: InvoiceStatus
    issued_at: datetime
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    billing_name: Optional[str] = None
    billing_email: Optional[str] = None
    created_at: datetime


class InvoiceListResponse(MongoBaseModel):
    total: int
    page: int
    pages: int
    limit: int
    data: list[InvoiceResponse]