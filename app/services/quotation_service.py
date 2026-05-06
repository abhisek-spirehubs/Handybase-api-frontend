from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from bson import ObjectId
from beanie.operators import In

from app.models.booking import Booking, BookingStatus
from app.models.quotation import Quotation, QuotationStatus
from app.models.service import Service
from app.models.user import User, UserRole
from app.schemas.client_features import (
    QuotationCreate,
    QuotationDecision,
    QuotationRespond,
)
from app.services.notification_service import NotificationService
from app.schemas.notification import NotificationCreate
from app.core.config import settings
from app.core.exceptions import (
    AppException, ForbiddenException,
    NotFoundException, ValidationException,
)
from app.utils.logger import app_logger

QUOTE_EXPIRY_HOURS = 48


def _utc_now() -> datetime:
    # Naive UTC — matches what MongoDB stores and returns
    return datetime.utcnow()


async def _get_fcm(user_id: str) -> Optional[str]:
    try:
        u = await User.get(user_id)
        return u.fcm_token if u else None
    except Exception:
        return None


# ── Client creates a quotation request ───────────────────────────────────────

async def create_quotation(
    client: User,
    data: QuotationCreate,
) -> Quotation:
    try:
        if not ObjectId.is_valid(data.service_id):
            raise ValidationException("Invalid service id")

        service = await Service.get(data.service_id)
        if not service or service.is_deleted or not service.is_active:
            raise NotFoundException("Service not found or unavailable")

        # One open quotation per client per service
        existing = await Quotation.find_one(
            Quotation.client_id  == str(client.id),
            Quotation.service_id == data.service_id,
            Quotation.is_deleted == False,
            In(Quotation.quotation_status, [
                QuotationStatus.PENDING,
                QuotationStatus.RESPONDED,
            ]),
        )
        if existing:
            raise ValidationException(
                "You already have an open quotation request for this service. "
                "Cancel the existing one before requesting a new one."
            )

        quotation = Quotation(
            client_id=str(client.id),
            provider_id=service.provider_id,
            service_id=data.service_id,
            message=data.message,
            preferred_date=data.preferred_date,
            address_line1=data.address_line1,
            address_line2=data.address_line2,
            city=data.city,
            state=data.state,
            postal_code=data.postal_code,
            country=data.country,
            created_by=str(client.id),
        )
        await quotation.insert()

        # Notify provider
        try:
            provider_token = await _get_fcm(service.provider_id)
            await NotificationService.create_notification(
                NotificationCreate(
                    user_id=service.provider_id,
                    title="New Quotation Request",
                    note=f'A client requested a quote for "{service.title}".',
                    type="QUOTATION_RECEIVED",
                    fcm_token=provider_token,
                    data={
                        "quotation_id": str(quotation.id),
                        "service_id":   data.service_id,
                        "type":         "QUOTATION_RECEIVED",
                    },
                )
            )
        except Exception as e:
            app_logger.error(
                "Quotation notify failed quotation_id=%s: %s", str(quotation.id), e
            )

        return quotation

    except AppException:
        raise
    except Exception:
        app_logger.exception("Failed to create quotation client_id=%s", str(client.id))
        raise AppException("Failed to submit quotation request", status_code=500)


# ── Provider responds with a price ────────────────────────────────────────────

async def respond_to_quotation(
    provider: User,
    quotation_id: str,
    data: QuotationRespond,
) -> Quotation:
    try:
        if not ObjectId.is_valid(quotation_id):
            raise ValidationException("Invalid quotation id")

        quotation = await Quotation.get(quotation_id)
        if not quotation or quotation.is_deleted:
            raise NotFoundException("Quotation not found")

        if quotation.provider_id != str(provider.id):
            raise ForbiddenException("This quotation does not belong to you")

        if quotation.quotation_status != QuotationStatus.PENDING:
            raise ValidationException(
                f"Cannot respond — quotation status is '{quotation.quotation_status}'"
            )

        now = _utc_now()
        quotation.quoted_price     = data.quoted_price
        quotation.provider_note    = data.provider_note
        quotation.responded_at     = now
        quotation.quotation_status = QuotationStatus.RESPONDED
        quotation.expires_at       = now + timedelta(hours=QUOTE_EXPIRY_HOURS)
        quotation.updated_by       = str(provider.id)
        await quotation.save()

        # Notify client
        try:
            client_token = await _get_fcm(quotation.client_id)
            await NotificationService.create_notification(
                NotificationCreate(
                    user_id=quotation.client_id,
                    title="Quotation Received",
                    note=f"A provider has responded with a price of "
                         f"\u20b9{data.quoted_price:,.2f}. Review and decide.",
                    type="QUOTATION_RESPONDED",
                    fcm_token=client_token,
                    data={
                        "quotation_id": str(quotation.id),
                        "quoted_price": str(data.quoted_price),
                        "type":         "QUOTATION_RESPONDED",
                    },
                )
            )
        except Exception as e:
            app_logger.error(
                "Quotation response notify failed quotation_id=%s: %s", quotation_id, e
            )

        return quotation

    except AppException:
        raise
    except Exception:
        app_logger.exception(
            "Failed to respond to quotation quotation_id=%s", quotation_id
        )
        raise AppException("Failed to respond to quotation", status_code=500)


# ── Client accepts or rejects ─────────────────────────────────────────────────

async def decide_quotation(
    client: User,
    quotation_id: str,
    data: QuotationDecision,
) -> Quotation:
    try:
        if not ObjectId.is_valid(quotation_id):
            raise ValidationException("Invalid quotation id")

        quotation = await Quotation.get(quotation_id)
        if not quotation or quotation.is_deleted:
            raise NotFoundException("Quotation not found")

        if quotation.client_id != str(client.id):
            raise ForbiddenException("This quotation does not belong to you")

        if quotation.quotation_status != QuotationStatus.RESPONDED:
            raise ValidationException(
                "You can only accept or reject a quotation that has been responded to"
            )

        now = _utc_now()

        # Check expiry — both sides are naive UTC now
        if quotation.expires_at and now > quotation.expires_at.replace(tzinfo=None):
            quotation.quotation_status = QuotationStatus.EXPIRED
            quotation.updated_by       = str(client.id)
            await quotation.save()
            raise ValidationException(
                "This quotation has expired. Please request a new one."
            )

        # ── Reject ────────────────────────────────────────────────────────
        if not data.accept:
            quotation.quotation_status = QuotationStatus.REJECTED
            quotation.updated_by       = str(client.id)
            await quotation.save()

            try:
                provider_token = await _get_fcm(quotation.provider_id)
                await NotificationService.create_notification(
                    NotificationCreate(
                        user_id=quotation.provider_id,
                        title="Quotation Rejected",
                        note="A client has declined your quotation.",
                        type="QUOTATION_REJECTED",
                        fcm_token=provider_token,
                        data={
                            "quotation_id": str(quotation.id),
                            "type":         "QUOTATION_REJECTED",
                        },
                    )
                )
            except Exception as e:
                app_logger.error("Quotation reject notify failed: %s", e)

            return quotation

        # ── Accept → convert to booking ───────────────────────────────────
        if not data.booking_date:
            raise ValidationException(
                "booking_date is required when accepting a quotation"
            )

        # Strip timezone from booking_date for comparison with naive UTC now
        booking_date_naive = data.booking_date.replace(tzinfo=None)
        if booking_date_naive <= now:
            raise ValidationException("booking_date must be in the future")

        service = await Service.get(quotation.service_id)
        if not service or service.is_deleted or not service.is_active:
            raise NotFoundException("Service is no longer available")

        # Availability check
        from app.services.availability_service import AvailabilityService
        is_available, reason = await AvailabilityService.is_slot_available(
            provider_id=service.provider_id,
            booking_date=data.booking_date,
            service_duration=service.duration,
        )
        if not is_available:
            raise AppException(reason, status_code=400)

        slot_end     = data.booking_date + timedelta(minutes=service.duration)
        gst_rate     = getattr(settings, "GST_RATE", 0.18)
        price        = quotation.quoted_price
        tax          = round(price * gst_rate, 2)
        total_amount = round(price + tax, 2)

        booking = Booking(
            client_id=str(client.id),
            provider_id=quotation.provider_id,
            service_id=quotation.service_id,
            booking_date=data.booking_date,
            slot_end=slot_end,
            note=quotation.message,
            idempotency_key=data.idempotency_key,
            price=price,
            gst_rate=gst_rate,
            tax=tax,
            total_amount=total_amount,
            booking_status=BookingStatus.PENDING,
            address_line1=quotation.address_line1,
            address_line2=quotation.address_line2,
            city=quotation.city,
            state=quotation.state,
            postal_code=quotation.postal_code,
            country=quotation.country,
            created_by=str(client.id),
        )
        await booking.insert()

        quotation.quotation_status = QuotationStatus.ACCEPTED
        quotation.booking_id       = str(booking.id)
        quotation.updated_by       = str(client.id)
        await quotation.save()

        # Notify provider
        try:
            provider_token = await _get_fcm(quotation.provider_id)
            await NotificationService.create_notification(
                NotificationCreate(
                    user_id=quotation.provider_id,
                    title="Quotation Accepted",
                    note="A client accepted your quotation and a booking has been created.",
                    type="QUOTATION_ACCEPTED",
                    fcm_token=provider_token,
                    data={
                        "quotation_id": str(quotation.id),
                        "booking_id":   str(booking.id),
                        "type":         "QUOTATION_ACCEPTED",
                    },
                )
            )
        except Exception as e:
            app_logger.error("Quotation accept notify failed: %s", e)

        return quotation

    except AppException:
        raise
    except Exception:
        app_logger.exception(
            "Failed to decide quotation quotation_id=%s", quotation_id
        )
        raise AppException("Failed to process quotation decision", status_code=500)


# ── Client cancels ────────────────────────────────────────────────────────────

async def cancel_quotation(client: User, quotation_id: str) -> Quotation:
    try:
        if not ObjectId.is_valid(quotation_id):
            raise ValidationException("Invalid quotation id")

        quotation = await Quotation.get(quotation_id)
        if not quotation or quotation.is_deleted:
            raise NotFoundException("Quotation not found")

        if quotation.client_id != str(client.id):
            raise ForbiddenException("This quotation does not belong to you")

        if quotation.quotation_status not in [
            QuotationStatus.PENDING,
            QuotationStatus.RESPONDED,
        ]:
            raise ValidationException(
                f"Cannot cancel a quotation with status '{quotation.quotation_status}'"
            )

        quotation.quotation_status = QuotationStatus.CANCELLED
        quotation.updated_by       = str(client.id)
        await quotation.save()
        return quotation

    except AppException:
        raise
    except Exception:
        app_logger.exception(
            "Failed to cancel quotation quotation_id=%s", quotation_id
        )
        raise AppException("Failed to cancel quotation", status_code=500)


# ── Paginated list helpers ────────────────────────────────────────────────────

async def get_client_quotations(
    client_id: str,
    status_filter: Optional[QuotationStatus],
    page: int,
    limit: int,
) -> dict:
    try:
        skip  = (page - 1) * limit
        query = [
            Quotation.client_id  == client_id,
            Quotation.is_deleted == False,
        ]
        if status_filter:
            query.append(Quotation.quotation_status == status_filter)

        total = await Quotation.find(*query).count()
        items = (
            await Quotation.find(*query)
            .sort("-created_at")
            .skip(skip)
            .limit(limit)
            .to_list()
        )
        return {
            "total": total,
            "page":  page,
            "limit": limit,
            "pages": max(1, (total + limit - 1) // limit),
            "data":  items,
        }
    except AppException:
        raise
    except Exception:
        app_logger.exception(
            "Failed to list client quotations client_id=%s", client_id
        )
        raise AppException("Failed to fetch quotations", status_code=500)


async def get_provider_quotations(
    provider_id: str,
    status_filter: Optional[QuotationStatus],
    page: int,
    limit: int,
) -> dict:
    try:
        skip  = (page - 1) * limit
        query = [
            Quotation.provider_id == provider_id,
            Quotation.is_deleted  == False,
        ]
        if status_filter:
            query.append(Quotation.quotation_status == status_filter)

        total = await Quotation.find(*query).count()
        items = (
            await Quotation.find(*query)
            .sort("-created_at")
            .skip(skip)
            .limit(limit)
            .to_list()
        )
        return {
            "total": total,
            "page":  page,
            "limit": limit,
            "pages": max(1, (total + limit - 1) // limit),
            "data":  items,
        }
    except AppException:
        raise
    except Exception:
        app_logger.exception(
            "Failed to list provider quotations provider_id=%s", provider_id
        )
        raise AppException("Failed to fetch quotations", status_code=500)


async def get_quotation_by_id(user: User, quotation_id: str) -> Quotation:
    try:
        if not ObjectId.is_valid(quotation_id):
            raise ValidationException("Invalid quotation id")

        quotation = await Quotation.get(quotation_id)
        if not quotation or quotation.is_deleted:
            raise NotFoundException("Quotation not found")

        if user.user_type == UserRole.ADMIN:
            return quotation

        if str(user.id) not in [quotation.client_id, quotation.provider_id]:
            raise ForbiddenException("Not allowed to view this quotation")

        return quotation

    except AppException:
        raise
    except Exception:
        app_logger.exception(
            "Failed to fetch quotation quotation_id=%s", quotation_id
        )
        raise AppException("Failed to fetch quotation", status_code=500)