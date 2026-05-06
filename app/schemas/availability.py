from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator
from app.models.provider_availability import DayOfWeek


# ── Request schemas ───────────────────────────────────────────────────────────

class TimeSlotInput(BaseModel):
    """
    Frontend sends HH:MM strings.
    Backend converts to minutes for storage.
    """
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", examples=["09:00"])
    end_time:   str = Field(..., pattern=r"^\d{2}:\d{2}$", examples=["17:00"])

    @model_validator(mode="after")
    def validate_times(self):
        start = self._to_minutes(self.start_time)
        end   = self._to_minutes(self.end_time)
        if end <= start:
            raise ValueError("end_time must be after start_time")
        return self

    @staticmethod
    def _to_minutes(t: str) -> int:
        h, m = map(int, t.split(":"))
        return h * 60 + m


class WeeklyScheduleInput(BaseModel):
    day:        DayOfWeek
    is_working: bool = True
    slots:      List[TimeSlotInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_slots(self):
        if self.is_working and not self.slots:
            raise ValueError(
                f"Working day '{self.day}' must have at least one time slot."
            )
        if not self.is_working:
            self.slots = []
        return self


class SetWeeklyScheduleRequest(BaseModel):
    """Provider sets their full weekly schedule in one call."""
    weekly_schedule: List[WeeklyScheduleInput] = Field(
        ...,
        min_length=1,
        max_length=7,
    )


class BlockDatesRequest(BaseModel):
    """Provider blocks specific dates — holidays, leaves etc."""
    dates: List[datetime] = Field(..., min_length=1)


class UnblockDatesRequest(BaseModel):
    """Provider unblocks previously blocked dates."""
    dates: List[datetime] = Field(..., min_length=1)


# ── Response schemas ──────────────────────────────────────────────────────────

class TimeSlotResponse(BaseModel):
    start_time: str     # HH:MM
    end_time:   str     # HH:MM


class WeeklyScheduleResponse(BaseModel):
    day:        DayOfWeek
    is_working: bool
    slots:      List[TimeSlotResponse]


class AvailabilityResponse(BaseModel):
    provider_id:     str
    weekly_schedule: List[WeeklyScheduleResponse]
    blocked_dates:   List[str]      # YYYY-MM-DD


class AvailableSlot(BaseModel):
    start_time:   str   # HH:MM UTC
    end_time:     str   # HH:MM UTC
    is_available: bool


class AvailableSlotsResponse(BaseModel):
    provider_id:      str
    date:             str   # YYYY-MM-DD
    service_duration: int   # minutes
    slots:            List[AvailableSlot]