from datetime import datetime, time
from typing import Optional, List
from enum import Enum
from pydantic import Field
from app.models.common import LogBase


class DayOfWeek(str, Enum):
    MONDAY    = "monday"
    TUESDAY   = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY  = "thursday"
    FRIDAY    = "friday"
    SATURDAY  = "saturday"
    SUNDAY    = "sunday"


class TimeSlot(LogBase):
    """
    A single working window within a day.
    e.g. 09:00 - 12:00, then 13:00 - 17:00 (with lunch break)
    Stored as minutes from midnight for easy arithmetic.
    e.g. 09:00 = 540, 17:00 = 1020
    """
    start_minute: int = Field(..., ge=0, lt=1440)   # 0 = 00:00, 1439 = 23:59
    end_minute:   int = Field(..., ge=1, le=1440)    # 1 = 00:01, 1440 = 24:00

    @property
    def start_time(self) -> str:
        h, m = divmod(self.start_minute, 60)
        return f"{h:02d}:{m:02d}"

    @property
    def end_time(self) -> str:
        h, m = divmod(self.end_minute, 60)
        return f"{h:02d}:{m:02d}"


class WeeklySchedule(LogBase):
    """One day entry in the provider's weekly schedule."""
    day:        DayOfWeek
    is_working: bool = True                 # False = day off
    slots:      List[TimeSlot] = Field(default_factory=list)
    # e.g. [09:00-12:00, 13:00-17:00] — handles lunch breaks


class ProviderAvailability(LogBase):
    """
    Provider's availability configuration.
    One document per provider.
    Updated whenever provider changes their schedule.

    weekly_schedule: recurring Mon-Sun pattern
    blocked_dates:   specific dates provider is unavailable
                     e.g. holidays, personal leaves
    """
    provider_id:     str
    weekly_schedule: List[WeeklySchedule] = Field(default_factory=list)
    blocked_dates:   List[datetime] = Field(default_factory=list)
    # blocked_dates stores date only — time component is ignored

    class Settings:
        name = "provider_availability"
        indexes = [
            "provider_id",
            # Unique constraint: one availability document per provider
            [("provider_id", 1), ("is_deleted", 1)],
        ]