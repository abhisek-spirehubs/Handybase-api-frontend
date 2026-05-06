from datetime import datetime, timezone, timedelta

from fastapi import BackgroundTasks
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.models.booking import Booking, BookingStatus
from app.models.chat_room import ChatRoom
from app.models.service import Service
from app.models.user import User, UserRole
from app.schemas.booking import BookingCreate, BookingUpdate
from app.utils.logger import app_logger
from app.core.config import settings
from app.core.exceptions import (
    AppException,
    NotFoundException,
    ForbiddenException,
    ValidationException,
    RateLimitException,
    ConflictException,
)

from app.services.notification_orchestrator import NotificationOrchestrator


class BookingService:

    # ─────────────────────────────────────────
    # Create
    # ─────────────────────────────────────────

    @staticmethod
    async def create_booking(
        client_id:        str,
        client_type:      UserRole,
        data:             BookingCreate,
        background_tasks: BackgroundTasks,
    ) -> tuple[Booking, bool]:
        """
        Returns (booking, was_created).

          was_created=True  → fresh booking, router returns 201.
          was_created=False → idempotency hit, original booking returned, router returns 200.

        Router is responsible for:
          - validating the Booking into BookingDataResponse
          - wrapping it in the APIResponse envelope
          - setting the correct HTTP status code based on was_created
        """
        try:
            if client_type != UserRole.CLIENT:
                raise ForbiddenException("Only clients can create bookings")

            from app.services.subscription_service import SubscriptionService
            features = await SubscriptionService.get_user_features(
                client_id, UserRole.CLIENT
            )
            if not features.can_book:
                raise ForbiddenException(
                    "Booking requires a paid client plan. Please upgrade."
                )

            if not ObjectId.is_valid(data.service_id):
                raise ValidationException("Invalid service id")

            service = await Service.get(data.service_id)
            if not service or service.is_deleted:
                raise NotFoundException("Service not found")
            if not service.is_active:
                raise AppException("Service is not available", status_code=400)

            # Rate limit — max 5 bookings per client per minute
            one_minute_ago = datetime.now(timezone.utc) - timedelta(minutes=1)
            recent_count = await Booking.find({
                "client_id":  client_id,
                "created_at": {"$gte": one_minute_ago},
            }).count()
            if recent_count >= 5:
                raise RateLimitException(
                    "Too many bookings. Please wait before trying again."
                )

            slot_end = data.booking_date + timedelta(minutes=service.duration)

            # ── Availability check ────────────────────────────────────────
            from app.services.availability_service import AvailabilityService
            is_available, reason = await AvailabilityService.is_slot_available(
                provider_id=service.provider_id,
                booking_date=data.booking_date,
                service_duration=service.duration,
            )
            if not is_available:
                raise AppException(reason, status_code=400)
            # ─────────────────────────────────────────────────────────────

            gst_rate     = getattr(settings, "GST_RATE", 0.18)
            price        = service.price
            tax          = round(price * gst_rate, 2)
            total_amount = round(price + tax, 2)

            booking = Booking(
                client_id=client_id,
                provider_id=service.provider_id,
                service_id=str(service.id),
                booking_date=data.booking_date,
                slot_end=slot_end,
                note=data.note,
                idempotency_key=data.idempotency_key,
                price=price,
                gst_rate=gst_rate,
                tax=tax,
                total_amount=total_amount,
                booking_status=BookingStatus.PENDING,
                address_line1=data.address_line1,
                address_line2=data.address_line2,
                city=data.city,
                state=data.state,
                postal_code=data.postal_code,
                country=data.country,
                created_by=client_id,
            )

            try:
                await booking.insert()
            except DuplicateKeyError:
                # Idempotency hit — return original booking with was_created=False
                # so the router can downgrade 201 → 200
                original = await Booking.find_one({"idempotency_key": data.idempotency_key})
                if original:
                    return original, False
                raise ConflictException("Duplicate booking request")

            # ── Notifications ─────────────────────────────────────────────
            background_tasks.add_task(
                NotificationOrchestrator.notify_user,
                user_id=client_id,
                title="Booking Placed",
                body="Your booking is submitted and awaiting provider confirmation.",
                notification_type="BOOKING_CREATED",
                background_tasks=background_tasks,
                data={"booking_id": str(booking.id), "type": "BOOKING_CREATED"},
                path=f"/bookings/{booking.id}",
                send_in_app=True,
                send_push=True,
            )

            background_tasks.add_task(
                NotificationOrchestrator.notify_user,
                user_id=service.provider_id,
                title="New Booking Request",
                body="You have received a new booking request. Please confirm or decline.",
                notification_type="BOOKING_REQUEST_RECEIVED",
                background_tasks=background_tasks,
                data={"booking_id": str(booking.id), "type": "BOOKING_REQUEST_RECEIVED"},
                path=f"/provider/bookings/{booking.id}",
                send_in_app=True,
                send_push=True,
            )

            return booking, True

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to create booking")
            raise AppException("Failed to create booking", status_code=500)

    # ─────────────────────────────────────────
    # Pagination helper
    # ─────────────────────────────────────────

    @staticmethod
    async def _paginated_bookings(query: dict, page: int, limit: int) -> dict:
        try:
            total = await Booking.find(query).count()
            skip  = (page - 1) * limit
            # Fetch the actual database documents
            docs  = await Booking.find(query).sort("-created_at").skip(skip).limit(limit).to_list()

            enriched_data = []
            for b in docs:
                # Convert the strict model to a flexible dictionary
                b_dict = b.model_dump()
                # Ensure the ID is a string for the frontend
                b_dict["id"] = str(b.id)

                # 1. Fetch Service Name
                service = await Service.get(b.service_id)
                b_dict["service_name"] = service.title if service else "Service Not Found"
                
                # 2. Fetch Provider Name
                provider = await User.get(b.provider_id)
                if provider:
                    b_dict["provider_name"] = getattr(provider, 'business_name', None) or provider.fname
                else:
                    b_dict["provider_name"] = "Unknown Provider"

                # 3. Fetch Client Name
                client = await User.get(b.client_id)
                if client:
                    b_dict["client_name"] = client.full_name or f"{client.fname or ''} {client.lname or ''}".strip() or client.email
                else:
                    b_dict["client_name"] = "Unknown Client"

                enriched_data.append(b_dict)

            return {
                "total": total,
                "data":  enriched_data, # Returning dictionaries is safe!
            }
        except Exception as e:
            app_logger.error("Failed to paginate bookings: {}", str(e))
            raise
    # ─────────────────────────────────────────
    # Read
    # ─────────────────────────────────────────

    @staticmethod
    async def get_client_bookings(client_id: str, page: int, limit: int) -> dict:
        try:
            return await BookingService._paginated_bookings(
                {"client_id": client_id, "is_deleted": False},
                page, limit,
            )
        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to fetch client bookings")
            raise AppException("Failed to fetch bookings", status_code=500)

    @staticmethod
    async def get_provider_bookings(provider_id: str, page: int, limit: int) -> dict:
        try:
            return await BookingService._paginated_bookings(
                {"provider_id": provider_id, "is_deleted": False},
                page, limit,
            )
        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to fetch provider bookings")
            raise AppException("Failed to fetch bookings", status_code=500)

    @staticmethod
    async def get_all_bookings(page: int, limit: int) -> dict:
        try:
            return await BookingService._paginated_bookings(
                {"is_deleted": False},
                page, limit,
            )
        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to fetch all bookings")
            raise AppException("Failed to fetch bookings", status_code=500)

    @staticmethod
    async def get_booking_by_id(booking_id: str, user_id: str) -> Booking:
        try:
            if not ObjectId.is_valid(booking_id):
                raise ValidationException("Invalid booking id")
            booking = await Booking.get(booking_id)
            if not booking or booking.is_deleted:
                raise NotFoundException("Booking not found")
            if user_id not in [booking.client_id, booking.provider_id]:
                raise ForbiddenException("Not allowed")
            return booking
        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to fetch booking")
            raise AppException("Failed to fetch booking", status_code=500)

    # ─────────────────────────────────────────
    # Update
    # ─────────────────────────────────────────

    @staticmethod
    async def update_booking(
        booking_id: str,
        client_id:  str,
        data:       BookingUpdate,
    ) -> Booking:
        try:
            if not ObjectId.is_valid(booking_id):
                raise ValidationException("Invalid booking id")
            booking = await Booking.get(booking_id)
            if not booking or booking.is_deleted:
                raise NotFoundException("Booking not found")
            if booking.client_id != client_id:
                raise ForbiddenException("Not allowed")
            if booking.booking_status != BookingStatus.PENDING:
                raise AppException(
                    "Only pending bookings can be modified. Cancel and rebook if changes are needed.",
                    status_code=409,
                    error_code="BOOKING_LOCKED",
                )

            update_data = data.model_dump(exclude_unset=True)

            if "booking_date" in update_data:
                service = await Service.get(booking.service_id)
                if not service:
                    raise NotFoundException("Associated service not found")

                new_slot_end = update_data["booking_date"] + timedelta(minutes=service.duration)
                update_data["slot_end"] = new_slot_end

                from app.services.availability_service import AvailabilityService
                is_available, reason = await AvailabilityService.is_slot_available(
                    provider_id=booking.provider_id,
                    booking_date=update_data["booking_date"],
                    service_duration=service.duration,
                )
                if not is_available:
                    raise AppException(reason, status_code=409, error_code="SLOT_UNAVAILABLE")

            for key, value in update_data.items():
                setattr(booking, key, value)

            booking.updated_by = client_id
            await booking.save()

            return booking

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to update booking")
            raise AppException("Failed to update booking", status_code=500)

    # ─────────────────────────────────────────
    # Delete
    # ─────────────────────────────────────────

    @staticmethod
    async def delete_booking(booking_id: str, client_id: str) -> Booking:
        """
        Soft-deletes the booking and returns the updated Booking document.
        Router reads deleted_at and deleted_by from the returned object
        to build the DeleteResponse.
        """
        try:
            if not ObjectId.is_valid(booking_id):
                raise ValidationException("Invalid booking id")
            booking = await Booking.get(booking_id)
            if not booking or booking.is_deleted:
                raise NotFoundException("Booking not found")
            if booking.client_id != client_id:
                raise ForbiddenException("Not allowed")
            if booking.booking_status in [BookingStatus.PENDING, BookingStatus.CONFIRMED]:
                raise AppException(
                    "Cannot delete an active booking. Cancel it first.",
                    status_code=400,
                    error_code="BOOKING_ACTIVE",
                )
            await booking.soft_delete(client_id)
            return booking  # deleted_at is stamped by soft_delete
        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to delete booking")
            raise AppException("Failed to delete booking", status_code=500)

    # ─────────────────────────────────────────
    # Status transitions
    # ─────────────────────────────────────────

    @staticmethod
    async def update_booking_status(
        booking_id:          str,
        user_id:             str,
        user_type:           UserRole,
        new_status:          BookingStatus,
        background_tasks:    BackgroundTasks,
        cancellation_reason: str | None = None,
    ) -> Booking:
        try:
            if not ObjectId.is_valid(booking_id):
                raise ValidationException("Invalid booking id")

            booking = await Booking.get(booking_id)
            if not booking or booking.is_deleted:
                raise NotFoundException("Booking not found")

            # ── Permission checks ─────────────────────────────────────────
            if new_status == BookingStatus.CONFIRMED:
                if user_id != booking.provider_id:
                    raise ForbiddenException("Only the provider can confirm a booking")
            elif new_status == BookingStatus.COMPLETED:
                if user_id != booking.provider_id:
                    raise ForbiddenException("Only the provider can complete a booking")
            elif new_status == BookingStatus.CANCELLED:
                if user_id not in [booking.client_id, booking.provider_id]:
                    raise ForbiddenException("Not allowed to cancel this booking")
                if not cancellation_reason:
                    raise AppException(
                        "Cancellation reason is required",
                        status_code=422,
                        error_code="VALIDATION_ERROR",
                    )

            # ── Allowed transitions ───────────────────────────────────────
            allowed_transitions: dict[BookingStatus, list[BookingStatus]] = {
                BookingStatus.PENDING:   [BookingStatus.CONFIRMED, BookingStatus.CANCELLED],
                BookingStatus.CONFIRMED: [BookingStatus.COMPLETED, BookingStatus.CANCELLED],
                BookingStatus.CANCELLED: [],
                BookingStatus.COMPLETED: [],
            }

            if new_status not in allowed_transitions.get(booking.booking_status, []):
                raise AppException(
                    f"Cannot transition from {booking.booking_status} to {new_status}",
                    status_code=409,
                    error_code="INVALID_TRANSITION",
                )

            now = datetime.now(timezone.utc)
            booking.booking_status = new_status
            booking.updated_by     = user_id

            # ── Status-specific actions + notifications ───────────────────
            if new_status == BookingStatus.CONFIRMED:
                booking.confirmed_by = user_id
                booking.confirmed_at = now

                existing_room = await ChatRoom.find_one({
                    "booking_id": str(booking.id),
                    "is_deleted": False,
                })
                if not existing_room:
                    await ChatRoom(
                        booking_id=str(booking.id),
                        client_id=booking.client_id,
                        provider_id=booking.provider_id,
                        created_by=user_id,
                    ).insert()

                background_tasks.add_task(
                    NotificationOrchestrator.notify_user,
                    user_id=booking.client_id,
                    title="Booking Confirmed",
                    body="Your booking is confirmed. You can now chat with your provider.",
                    notification_type="BOOKING_CONFIRMED",
                    background_tasks=background_tasks,
                    data={"booking_id": str(booking.id), "type": "BOOKING_CONFIRMED"},
                    path=f"/bookings/{booking.id}",
                    send_in_app=True,
                    send_push=True,
                )
                background_tasks.add_task(
                    NotificationOrchestrator.notify_user,
                    user_id=booking.provider_id,
                    title="Chat Opened",
                    body="Booking confirmed. You can now chat with your client.",
                    notification_type="CHAT_OPENED",
                    background_tasks=background_tasks,
                    data={"booking_id": str(booking.id), "type": "CHAT_OPENED"},
                    path=f"/provider/bookings/{booking.id}",
                    send_in_app=True,
                    send_push=True,
                )

            elif new_status == BookingStatus.CANCELLED:
                booking.cancelled_by        = user_id
                booking.cancelled_at        = now
                booking.cancellation_reason = cancellation_reason

                if user_id == booking.client_id:
                    background_tasks.add_task(
                        NotificationOrchestrator.notify_user,
                        user_id=booking.provider_id,
                        title="Booking Cancelled",
                        body="A client has cancelled their booking.",
                        notification_type="BOOKING_CANCELLED",
                        background_tasks=background_tasks,
                        data={"booking_id": str(booking.id), "type": "BOOKING_CANCELLED"},
                        path=f"/provider/bookings/{booking.id}",
                        send_in_app=True,
                        send_push=True,
                    )
                else:
                    background_tasks.add_task(
                        NotificationOrchestrator.notify_user,
                        user_id=booking.client_id,
                        title="Booking Cancelled",
                        body="Your booking has been cancelled by the provider.",
                        notification_type="BOOKING_CANCELLED",
                        background_tasks=background_tasks,
                        data={"booking_id": str(booking.id), "type": "BOOKING_CANCELLED"},
                        path=f"/bookings/{booking.id}",
                        send_in_app=True,
                        send_push=True,
                    )

            elif new_status == BookingStatus.COMPLETED:
                booking.completed_at = now
                background_tasks.add_task(
                    NotificationOrchestrator.notify_user,
                    user_id=booking.client_id,
                    title="Booking Completed",
                    body="Your service has been completed. Please leave a review.",
                    notification_type="BOOKING_COMPLETED",
                    background_tasks=background_tasks,
                    data={"booking_id": str(booking.id), "type": "BOOKING_COMPLETED"},
                    path=f"/bookings/{booking.id}",
                    send_in_app=True,
                    send_push=True,
                )

            await booking.save()

            return booking

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to update booking status")
            raise AppException("Failed to update booking status", status_code=500)
