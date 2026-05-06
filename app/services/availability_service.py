from datetime import datetime, timedelta
from typing import Optional, List

from app.models.provider_availability import (
    ProviderAvailability,
    WeeklySchedule,
    TimeSlot,
    DayOfWeek,
)
from app.models.user import User
from app.schemas.availability import (
    SetWeeklyScheduleRequest,
    BlockDatesRequest,
    UnblockDatesRequest,
    AvailabilityResponse,
    WeeklyScheduleResponse,
    TimeSlotResponse,
    AvailableSlot,
    AvailableSlotsResponse,
)
from app.utils.logger import app_logger
from app.core.exceptions import (
    NotFoundException,
    ForbiddenException,
    ValidationException,
    AppException,
)


# ── Day of week mapping ───────────────────────────────────────────────────────
_WEEKDAY_MAP = {
    0: DayOfWeek.MONDAY,
    1: DayOfWeek.TUESDAY,
    2: DayOfWeek.WEDNESDAY,
    3: DayOfWeek.THURSDAY,
    4: DayOfWeek.FRIDAY,
    5: DayOfWeek.SATURDAY,
    6: DayOfWeek.SUNDAY,
}


def _to_minutes(time_str: str) -> int:
    """Convert HH:MM string to minutes from midnight."""
    h, m = map(int, time_str.split(":"))
    return h * 60 + m


def _from_minutes(minutes: int) -> str:
    """Convert minutes from midnight to HH:MM string."""
    h, m = divmod(minutes, 60)
    return f"{h:02d}:{m:02d}"


def _date_only(dt: datetime) -> datetime:
    """Strip time component — keep date only."""
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


class AvailabilityService:

    # ─────────────────────────────────────────
    # Get or create availability document
    # ─────────────────────────────────────────

    @staticmethod
    async def _get_or_create(provider_id: str) -> ProviderAvailability:
        """
        Returns existing availability document or creates empty one.
        Every provider gets one availability document.
        """
        availability = await ProviderAvailability.find_one(
            ProviderAvailability.provider_id == provider_id,
            ProviderAvailability.is_deleted == False,
        )
        if not availability:
            availability = ProviderAvailability(
                provider_id=provider_id,
                weekly_schedule=[],
                blocked_dates=[],
                created_by=provider_id,
            )
            await availability.insert()
        return availability

    # ─────────────────────────────────────────
    # Set weekly schedule
    # ─────────────────────────────────────────

    @staticmethod
    async def set_weekly_schedule(
        provider_id: str,
        data: SetWeeklyScheduleRequest,
    ) -> AvailabilityResponse:
        """
        Provider sets their weekly recurring schedule.
        Replaces existing schedule completely.
        Tier 2+ only — checked at endpoint level.
        """
        try:
            availability = await AvailabilityService._get_or_create(provider_id)

            schedule = []
            for day_input in data.weekly_schedule:
                slots = []
                for slot_input in day_input.slots:
                    start = _to_minutes(slot_input.start_time)
                    end   = _to_minutes(slot_input.end_time)

                    # Validate no overlapping slots within same day
                    for existing_slot in slots:
                        if start < existing_slot.end_minute and end > existing_slot.start_minute:
                            raise ValidationException(
                                f"Overlapping time slots on {day_input.day}: "
                                f"{slot_input.start_time}-{slot_input.end_time}"
                            )

                    slots.append(TimeSlot(
                        start_minute=start,
                        end_minute=end,
                        created_by=provider_id,
                    ))

                schedule.append(WeeklySchedule(
                    day=day_input.day,
                    is_working=day_input.is_working,
                    slots=slots,
                    created_by=provider_id,
                ))

            availability.weekly_schedule = schedule
            availability.updated_by      = provider_id
            await availability.save()

            app_logger.info(
                "Weekly schedule updated provider_id=%s days=%d",
                provider_id, len(schedule),
            )

            return AvailabilityService._to_response(availability)

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to set weekly schedule provider_id=%s", provider_id
            )
            raise AppException("Failed to update schedule", status_code=500)

    # ─────────────────────────────────────────
    # Block dates
    # ─────────────────────────────────────────

    @staticmethod
    async def block_dates(
        provider_id: str,
        data: BlockDatesRequest,
    ) -> AvailabilityResponse:
        """
        Provider blocks specific dates — holidays, leaves etc.
        Existing bookings on those dates are NOT auto-cancelled.
        """
        try:
            availability = await AvailabilityService._get_or_create(provider_id)

            existing  = {_date_only(d) for d in availability.blocked_dates}
            new_dates = {_date_only(d) for d in data.dates}
            merged    = sorted(existing | new_dates)

            availability.blocked_dates = list(merged)
            availability.updated_by    = provider_id
            await availability.save()

            app_logger.info(
                "Dates blocked provider_id=%s count=%d",
                provider_id, len(data.dates),
            )

            return AvailabilityService._to_response(availability)

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to block dates provider_id=%s", provider_id
            )
            raise AppException("Failed to block dates", status_code=500)

    # ─────────────────────────────────────────
    # Unblock dates
    # ─────────────────────────────────────────

    @staticmethod
    async def unblock_dates(
        provider_id: str,
        data: UnblockDatesRequest,
    ) -> AvailabilityResponse:
        """Provider removes previously blocked dates."""
        try:
            availability = await AvailabilityService._get_or_create(provider_id)

            to_remove = {_date_only(d) for d in data.dates}
            availability.blocked_dates = [
                d for d in availability.blocked_dates
                if _date_only(d) not in to_remove
            ]
            availability.updated_by = provider_id
            await availability.save()

            return AvailabilityService._to_response(availability)

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to unblock dates provider_id=%s", provider_id
            )
            raise AppException("Failed to unblock dates", status_code=500)

    # ─────────────────────────────────────────
    # Get availability
    # ─────────────────────────────────────────

    @staticmethod
    async def get_availability(provider_id: str) -> AvailabilityResponse:
        """Returns provider's full availability configuration."""
        try:
            availability = await AvailabilityService._get_or_create(provider_id)
            return AvailabilityService._to_response(availability)
        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to get availability provider_id=%s", provider_id
            )
            raise AppException("Failed to get availability", status_code=500)

    # ─────────────────────────────────────────
    # Get available slots for a date
    # ─────────────────────────────────────────

    @staticmethod
    async def get_available_slots(
        provider_id: str,
        date: datetime,
        service_duration: int,
    ) -> AvailableSlotsResponse:
        """
        Returns all time slots for a provider on a specific date.
        Based ONLY on provider working hours — does NOT check
        existing bookings. Overlap is handled at booking creation time.

        All slots within working hours are marked is_available=True.
        """
        try:
            date_only = _date_only(date)
            date_str  = date_only.strftime("%Y-%m-%d")

            availability = await AvailabilityService._get_or_create(provider_id)

            # ── Check if date is blocked ──────────────────────────────
            is_blocked = any(
                _date_only(d) == date_only
                for d in availability.blocked_dates
            )
            if is_blocked:
                return AvailableSlotsResponse(
                    provider_id=provider_id,
                    date=date_str,
                    service_duration=service_duration,
                    slots=[],
                )

            # ── Get weekly schedule for day of week ───────────────────
            day_of_week  = _WEEKDAY_MAP[date_only.weekday()]
            day_schedule = next(
                (s for s in availability.weekly_schedule if s.day == day_of_week),
                None,
            )

            # No schedule or day is off
            if not day_schedule or not day_schedule.is_working or not day_schedule.slots:
                return AvailableSlotsResponse(
                    provider_id=provider_id,
                    date=date_str,
                    service_duration=service_duration,
                    slots=[],
                )

            # ── Generate slots from working hours ─────────────────────
            # Slide through each working window in service_duration steps
            # All slots marked available — no booking overlap check here
            available_slots = []

            for working_slot in day_schedule.slots:
                current = working_slot.start_minute

                while current + service_duration <= working_slot.end_minute:
                    slot_end = current + service_duration

                    available_slots.append(AvailableSlot(
                        start_time=_from_minutes(current),
                        end_time=_from_minutes(slot_end),
                        is_available=True,
                    ))

                    current += service_duration

            return AvailableSlotsResponse(
                provider_id=provider_id,
                date=date_str,
                service_duration=service_duration,
                slots=available_slots,
            )

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to get available slots provider_id=%s", provider_id
            )
            raise AppException("Failed to get available slots", status_code=500)

    # ─────────────────────────────────────────
    # Check if slot is available
    # Called by booking_service before creating booking
    # ─────────────────────────────────────────

    @staticmethod
    async def is_slot_available(
        provider_id: str,
        booking_date: datetime,
        service_duration: int,
    ) -> tuple[bool, str]:
        """
        Checks ONLY if provider is working on that day and time.
        Does NOT check existing bookings — overlap is handled
        separately in booking_service.py.

        Returns:
            (True, "")               → provider is working this slot
            (False, "reason string") → provider is not available
        """
        try:
            date_only    = _date_only(booking_date)
            availability = await AvailabilityService._get_or_create(provider_id)

            # No schedule set — provider has not configured calendar yet
            # Allow booking — backwards compatible with Tier 1 providers
            if not availability.weekly_schedule:
                return True, ""

            # ── Check blocked dates ───────────────────────────────────
            is_blocked = any(
                _date_only(d) == date_only
                for d in availability.blocked_dates
            )
            if is_blocked:
                return False, "Provider is not available on this date"

            # ── Check weekly schedule ─────────────────────────────────
            day_of_week  = _WEEKDAY_MAP[date_only.weekday()]
            day_schedule = next(
                (s for s in availability.weekly_schedule if s.day == day_of_week),
                None,
            )

            if not day_schedule or not day_schedule.is_working:
                return False, f"Provider does not work on {day_of_week.value.capitalize()}s"

            if not day_schedule.slots:
                return False, "Provider has no availability set for this day"

            # ── Check requested time falls within a working slot ──────
            req_start = booking_date.hour * 60 + booking_date.minute
            req_end   = req_start + service_duration

            fits_in_slot = any(
                slot.start_minute <= req_start and req_end <= slot.end_minute
                for slot in day_schedule.slots
            )

            if not fits_in_slot:
                return False, "Requested time is outside provider working hours"

            return True, ""

        except Exception as e:
            app_logger.error(
                "Availability check failed provider_id=%s: %s", provider_id, e
            )
            # On error — allow booking, do not block client
            return True, ""

    # ─────────────────────────────────────────
    # Internal — convert model to response
    # ─────────────────────────────────────────

    @staticmethod
    def _to_response(availability: ProviderAvailability) -> AvailabilityResponse:
        schedule = []
        for day in availability.weekly_schedule:
            slots = [
                TimeSlotResponse(
                    start_time=_from_minutes(s.start_minute),
                    end_time=_from_minutes(s.end_minute),
                )
                for s in day.slots
            ]
            schedule.append(WeeklyScheduleResponse(
                day=day.day,
                is_working=day.is_working,
                slots=slots,
            ))

        blocked = [
            _date_only(d).strftime("%Y-%m-%d")
            for d in availability.blocked_dates
        ]

        return AvailabilityResponse(
            provider_id=availability.provider_id,
            weekly_schedule=schedule,
            blocked_dates=sorted(blocked),
        )