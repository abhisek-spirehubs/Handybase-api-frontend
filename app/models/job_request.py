from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel
from app.models.common import BaseLogWithStatus


class JobRequestStatus(str, Enum):
    OPEN      = "OPEN"
    ASSIGNED  = "ASSIGNED"
    CLOSED    = "CLOSED"
    CANCELLED = "CANCELLED"


class JobApplicationStatus(str, Enum):
    PENDING  = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class JobLocation(BaseModel):
    """
    Pinned Google Maps location embedded in JobRequest.
    Only returned to provider after their application is ACCEPTED
    and only while the linked booking is PENDING or CONFIRMED.
    """
    place_id:     Optional[str]   = None
    place_name:   Optional[str]   = None
    latitude:     Optional[float] = None
    longitude:    Optional[float] = None
    address_text: Optional[str]   = None


class JobRequest(BaseLogWithStatus):
    """
    Client posts a job open to multiple providers.
    Providers apply with their price -> client picks one -> booking auto-created.
    """
    client_id:    str
    category_id:  str
    title:        str
    description:  Optional[str]   = None
    budget:       Optional[float] = None
    preferred_date: Optional[datetime] = None

    location: Optional[JobLocation] = None

    address_line1: str
    address_line2: Optional[str] = None
    city:          str
    state:         str
    postal_code:   str
    country:       str

    job_status:           JobRequestStatus = JobRequestStatus.OPEN
    assigned_provider_id: Optional[str]    = None
    assigned_booking_id:  Optional[str]    = None
    application_count:    int              = 0

    class Settings:
        name = "job_requests"
        indexes = [
            [("client_id",   1), ("is_deleted", 1), ("created_at", -1)],
            [("category_id", 1), ("job_status",  1), ("created_at", -1)],
            [("job_status",  1), ("created_at",  -1)],
            # Additional indexes for common queries
            [("job_status", 1), ("category_id", 1), ("created_at", -1)],  # browse open jobs
            [("city", 1), ("state", 1), ("job_status", 1)],  # location-based job search
            [("assigned_provider_id", 1), ("job_status", 1)],  # provider's assigned jobs
            [("preferred_date", 1)],  # date-based filtering
        ]


class JobApplication(BaseLogWithStatus):
    """
    Provider's bid on a JobRequest.
    One application per provider per job (compound index enforced).
    """
    job_request_id: str
    provider_id:    str
    client_id:      str

    quoted_price:   float
    note:           Optional[str] = None

    application_status: JobApplicationStatus = JobApplicationStatus.PENDING

    class Settings:
        name = "job_applications"
        indexes = [
            [("job_request_id", 1), ("provider_id", 1), ("is_deleted", 1)],
            [("job_request_id", 1), ("application_status", 1)],
            [("provider_id",    1), ("is_deleted", 1), ("created_at", -1)],
            [("client_id",      1), ("is_deleted", 1), ("created_at", -1)],
            # Additional indexes
            [("provider_id", 1), ("application_status", 1), ("created_at", -1)],  # provider's pending applications
            [("job_request_id", 1), ("application_status", 1), ("quoted_price", 1)],  # sort by price
        ]