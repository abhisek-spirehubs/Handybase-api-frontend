from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId

from app.models.booking import Booking, BookingStatus
from app.models.job_request import (
    JobApplication, JobApplicationStatus,
    JobLocation, JobRequest, JobRequestStatus,
)
from app.models.service import Service
from app.models.user import User, UserRole
from app.schemas.job_request import (
    JobApplicationCreate,
    JobRequestCreate,
    JobRequestUpdate,
    SelectProviderRequest,
)
from app.services.notification_service import NotificationService
from app.schemas.notification import NotificationCreate
from app.core.config import settings
from app.core.exceptions import (
    AppException, ForbiddenException,
    NotFoundException, ValidationException,
)
from app.utils.logger import app_logger


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _get_fcm(user_id: str) -> Optional[str]:
    try:
        u = await User.get(user_id)
        return u.fcm_token if u else None
    except Exception:
        return None


def _should_show_location(
    job: JobRequest,
    caller_user_id: str,
    caller_role: UserRole,
    linked_booking: Optional[Booking],
) -> bool:
    """
    Location is visible to a provider ONLY when:
    1. They are the assigned provider for this job, AND
    2. The linked booking is PENDING or CONFIRMED (i.e. still active)

    Clients and admins always see the location.
    """
    if caller_role in [UserRole.CLIENT, UserRole.ADMIN]:
        return True

    if caller_role == UserRole.PROVIDER:
        if job.assigned_provider_id != caller_user_id:
            return False
        if linked_booking is None:
            return False
        return linked_booking.booking_status in [
            BookingStatus.PENDING,
            BookingStatus.CONFIRMED,
        ]

    return False


# ── Client creates a job request ──────────────────────────────────────────────

async def create_job_request(client: User, data: JobRequestCreate) -> JobRequest:
    try:
        if not ObjectId.is_valid(data.category_id):
            raise ValidationException("Invalid category id")

        location = None
        if data.location:
            location = JobLocation(
                place_id=data.location.place_id,
                place_name=data.location.place_name,
                latitude=data.location.latitude,
                longitude=data.location.longitude,
                address_text=data.location.address_text,
            )

        job = JobRequest(
            client_id=str(client.id),
            category_id=data.category_id,
            title=data.title,
            description=data.description,
            budget=data.budget,
            preferred_date=data.preferred_date,
            location=location,
            address_line1=data.address_line1,
            address_line2=data.address_line2,
            city=data.city,
            state=data.state,
            postal_code=data.postal_code,
            country=data.country,
            created_by=str(client.id),
        )
        await job.insert()

        # Notify all approved providers in this category
        try:
            from app.models.service import Service, ServiceApprovalStatus
            provider_ids = await Service.find(
                Service.category_id == data.category_id,
                Service.is_deleted == False,
                Service.is_active == True,
                Service.approval_status == ServiceApprovalStatus.APPROVED,
            ).distinct("provider_id")

            for pid in provider_ids[:50]:   # cap at 50 to avoid notification flood
                token = await _get_fcm(str(pid))
                await NotificationService.create_notification(
                    NotificationCreate(
                        user_id=str(pid),
                        title="New Job Request",
                        note=f'A client is looking for help with "{data.title}". Apply now.',
                        type="JOB_REQUEST_POSTED",
                        fcm_token=token,
                        data={
                            "job_request_id": str(job.id),
                            "type":           "JOB_REQUEST_POSTED",
                        },
                    )
                )
        except Exception as e:
            app_logger.error("Job request notify failed job_id=%s: %s", str(job.id), e)

        return job

    except AppException:
        raise
    except Exception:
        app_logger.exception("Failed to create job request client_id=%s", str(client.id))
        raise AppException("Failed to create job request", status_code=500)


# ── Client updates a job request (OPEN only) ─────────────────────────────────

async def update_job_request(
    client: User,
    job_id: str,
    data: JobRequestUpdate,
) -> JobRequest:
    try:
        if not ObjectId.is_valid(job_id):
            raise ValidationException("Invalid job request id")

        job = await JobRequest.get(job_id)
        if not job or job.is_deleted:
            raise NotFoundException("Job request not found")

        if job.client_id != str(client.id):
            raise ForbiddenException("Not your job request")

        if job.job_status != JobRequestStatus.OPEN:
            raise ValidationException("Only OPEN job requests can be edited")

        if data.title is not None:
            job.title = data.title
        if data.description is not None:
            job.description = data.description
        if data.budget is not None:
            job.budget = data.budget
        if data.preferred_date is not None:
            job.preferred_date = data.preferred_date
        if data.location is not None:
            job.location = JobLocation(**data.location.model_dump())

        job.updated_by = str(client.id)
        await job.save()
        return job

    except AppException:
        raise
    except Exception:
        app_logger.exception("Failed to update job request job_id=%s", job_id)
        raise AppException("Failed to update job request", status_code=500)


# ── Client cancels a job request ─────────────────────────────────────────────

async def cancel_job_request(client: User, job_id: str) -> JobRequest:
    try:
        if not ObjectId.is_valid(job_id):
            raise ValidationException("Invalid job request id")

        job = await JobRequest.get(job_id)
        if not job or job.is_deleted:
            raise NotFoundException("Job request not found")

        if job.client_id != str(client.id):
            raise ForbiddenException("Not your job request")

        if job.job_status not in [JobRequestStatus.OPEN]:
            raise ValidationException(
                f"Cannot cancel a job request with status '{job.job_status}'"
            )

        job.job_status = JobRequestStatus.CANCELLED
        job.updated_by = str(client.id)
        await job.save()
        return job

    except AppException:
        raise
    except Exception:
        app_logger.exception("Failed to cancel job request job_id=%s", job_id)
        raise AppException("Failed to cancel job request", status_code=500)


# ── Provider applies to a job request ────────────────────────────────────────

async def apply_to_job(
    provider: User,
    job_id: str,
    data: JobApplicationCreate,
) -> JobApplication:
    try:
        if not ObjectId.is_valid(job_id):
            raise ValidationException("Invalid job request id")

        job = await JobRequest.get(job_id)
        if not job or job.is_deleted:
            raise NotFoundException("Job request not found")

        if job.job_status != JobRequestStatus.OPEN:
            raise ValidationException("This job request is no longer accepting applications")

        if job.client_id == str(provider.id):
            raise ForbiddenException("You cannot apply to your own job request")

        # One application per provider per job
        existing = await JobApplication.find_one(
            JobApplication.job_request_id == job_id,
            JobApplication.provider_id    == str(provider.id),
            JobApplication.is_deleted     == False,
        )
        if existing:
            raise ValidationException(
                "You have already applied to this job request. "
                "Delete your existing application to reapply."
            )

        application = JobApplication(
            job_request_id=job_id,
            provider_id=str(provider.id),
            client_id=job.client_id,
            quoted_price=data.quoted_price,
            note=data.note,
            created_by=str(provider.id),
        )
        await application.insert()

        # Update application count cache
        job.application_count += 1
        await job.save()

        # Notify client
        try:
            client_token = await _get_fcm(job.client_id)
            await NotificationService.create_notification(
                NotificationCreate(
                    user_id=job.client_id,
                    title="New Application",
                    note=f'A provider has applied to your job "{job.title}".',
                    type="JOB_APPLICATION_RECEIVED",
                    fcm_token=client_token,
                    data={
                        "job_request_id":  job_id,
                        "application_id":  str(application.id),
                        "type":            "JOB_APPLICATION_RECEIVED",
                    },
                )
            )
        except Exception as e:
            app_logger.error("Application notify failed: %s", e)

        return application

    except AppException:
        raise
    except Exception:
        app_logger.exception(
            "Failed to apply to job provider_id=%s job_id=%s",
            str(provider.id), job_id,
        )
        raise AppException("Failed to submit application", status_code=500)


# ── Provider withdraws application ───────────────────────────────────────────

async def withdraw_application(provider: User, application_id: str) -> None:
    try:
        if not ObjectId.is_valid(application_id):
            raise ValidationException("Invalid application id")

        application = await JobApplication.get(application_id)
        if not application or application.is_deleted:
            raise NotFoundException("Application not found")

        if application.provider_id != str(provider.id):
            raise ForbiddenException("Not your application")

        if application.application_status != JobApplicationStatus.PENDING:
            raise ValidationException("Only PENDING applications can be withdrawn")

        await application.soft_delete(str(provider.id))

        # Decrement count cache
        job = await JobRequest.get(application.job_request_id)
        if job and job.application_count > 0:
            job.application_count -= 1
            await job.save()

    except AppException:
        raise
    except Exception:
        app_logger.exception("Failed to withdraw application application_id=%s", application_id)
        raise AppException("Failed to withdraw application", status_code=500)


# ── Client selects a provider → booking auto-created ─────────────────────────

async def select_provider(
    client: User,
    job_id: str,
    data: SelectProviderRequest,
) -> JobRequest:
    try:
        if not ObjectId.is_valid(job_id):
            raise ValidationException("Invalid job request id")

        if not ObjectId.is_valid(data.application_id):
            raise ValidationException("Invalid application id")

        job = await JobRequest.get(job_id)
        if not job or job.is_deleted:
            raise NotFoundException("Job request not found")

        if job.client_id != str(client.id):
            raise ForbiddenException("Not your job request")

        if job.job_status != JobRequestStatus.OPEN:
            raise ValidationException(
                f"Cannot assign a provider — job is '{job.job_status}'"
            )

        application = await JobApplication.get(data.application_id)
        if not application or application.is_deleted:
            raise NotFoundException("Application not found")

        if application.job_request_id != job_id:
            raise ValidationException("Application does not belong to this job request")

        if application.application_status != JobApplicationStatus.PENDING:
            raise ValidationException("This application is no longer available")

        if data.booking_date <= _utc_now():
            raise ValidationException("booking_date must be in the future")

        # ── Find the provider's service in this category ──────────────
        service = await Service.find_one(
            Service.provider_id   == application.provider_id,
            Service.category_id   == job.category_id,
            Service.is_active     == True,
            Service.is_deleted    == False,
        )
        if not service:
            raise AppException(
                "Provider does not have an active service in this category",
                status_code=400,
            )

        # ── Availability check ────────────────────────────────────────
        from app.services.availability_service import AvailabilityService
        is_available, reason = await AvailabilityService.is_slot_available(
            provider_id=application.provider_id,
            booking_date=data.booking_date,
            service_duration=service.duration,
        )
        if not is_available:
            raise AppException(reason, status_code=400)

        # ── Create booking with quoted price ─────────────────────────
        from datetime import timedelta
        slot_end     = data.booking_date + timedelta(minutes=service.duration)
        gst_rate     = getattr(settings, "GST_RATE", 0.18)
        price        = application.quoted_price
        tax          = round(price * gst_rate, 2)
        total_amount = round(price + tax, 2)

        booking = Booking(
            client_id=str(client.id),
            provider_id=application.provider_id,
            service_id=str(service.id),
            booking_date=data.booking_date,
            slot_end=slot_end,
            note=job.description,
            idempotency_key=data.idempotency_key,
            price=price,
            gst_rate=gst_rate,
            tax=tax,
            total_amount=total_amount,
            booking_status=BookingStatus.PENDING,
            address_line1=job.address_line1,
            address_line2=job.address_line2,
            city=job.city,
            state=job.state,
            postal_code=job.postal_code,
            country=job.country,
            created_by=str(client.id),
        )
        await booking.insert()

        # ── Accept winning application ────────────────────────────────
        application.application_status = JobApplicationStatus.ACCEPTED
        application.updated_by         = str(client.id)
        await application.save()

        # ── Reject all other applications ────────────────────────────
        others = await JobApplication.find(
            JobApplication.job_request_id    == job_id,
            JobApplication.is_deleted        == False,
            JobApplication.application_status == JobApplicationStatus.PENDING,
        ).to_list()

        for other in others:
            if str(other.id) != data.application_id:
                other.application_status = JobApplicationStatus.REJECTED
                other.updated_by         = str(client.id)
                await other.save()

        # ── Close job request ─────────────────────────────────────────
        job.job_status           = JobRequestStatus.ASSIGNED
        job.assigned_provider_id = application.provider_id
        job.assigned_booking_id  = str(booking.id)
        job.updated_by           = str(client.id)
        await job.save()

        # ── Notifications ─────────────────────────────────────────────
        try:
            provider_token = await _get_fcm(application.provider_id)
            await NotificationService.create_notification(
                NotificationCreate(
                    user_id=application.provider_id,
                    title="You've Been Selected!",
                    note=f'You were selected for the job "{job.title}". A booking has been created.',
                    type="JOB_APPLICATION_ACCEPTED",
                    fcm_token=provider_token,
                    data={
                        "job_request_id": job_id,
                        "booking_id":     str(booking.id),
                        "type":           "JOB_APPLICATION_ACCEPTED",
                    },
                )
            )
            # Notify rejected providers
            for other in others:
                if str(other.id) != data.application_id:
                    token = await _get_fcm(other.provider_id)
                    await NotificationService.create_notification(
                        NotificationCreate(
                            user_id=other.provider_id,
                            title="Application Not Selected",
                            note=f'Another provider was selected for "{job.title}".',
                            type="JOB_APPLICATION_REJECTED",
                            fcm_token=token,
                            data={
                                "job_request_id": job_id,
                                "type":           "JOB_APPLICATION_REJECTED",
                            },
                        )
                    )
        except Exception as e:
            app_logger.error("Selection notify failed job_id=%s: %s", job_id, e)

        return job

    except AppException:
        raise
    except Exception:
        app_logger.exception(
            "Failed to select provider job_id=%s application_id=%s",
            job_id, data.application_id,
        )
        raise AppException("Failed to assign provider", status_code=500)


# ── Get single job request (with location visibility logic) ──────────────────

async def get_job_request(caller: User, job_id: str) -> dict:
    """
    Returns job request. Location field is stripped unless:
    - caller is the client who owns it, OR
    - caller is the assigned provider AND booking is still active, OR
    - caller is admin
    """
    try:
        if not ObjectId.is_valid(job_id):
            raise ValidationException("Invalid job request id")

        job = await JobRequest.get(job_id)
        if not job or job.is_deleted:
            raise NotFoundException("Job request not found")

        # Access check — providers can see OPEN jobs, clients see own
        if caller.user_type == UserRole.CLIENT and job.client_id != str(caller.id):
            raise ForbiddenException("Not your job request")

        # Fetch linked booking if assigned
        linked_booking = None
        if job.assigned_booking_id:
            try:
                linked_booking = await Booking.get(job.assigned_booking_id)
            except Exception:
                pass

        show_location = _should_show_location(
            job=job,
            caller_user_id=str(caller.id),
            caller_role=caller.user_type,
            linked_booking=linked_booking,
        )

        return {"job": job, "show_location": show_location}

    except AppException:
        raise
    except Exception:
        app_logger.exception("Failed to fetch job request job_id=%s", job_id)
        raise AppException("Failed to fetch job request", status_code=500)


# ── Paginated list helpers ────────────────────────────────────────────────────

async def list_client_job_requests(
    client_id: str,
    status: Optional[JobRequestStatus],
    page: int,
    limit: int,
) -> dict:
    try:
        skip  = (page - 1) * limit
        query = [JobRequest.client_id == client_id, JobRequest.is_deleted == False]
        if status:
            query.append(JobRequest.job_status == status)

        total = await JobRequest.find(*query).count()
        items = (
            await JobRequest.find(*query)
            .sort("-created_at").skip(skip).limit(limit).to_list()
        )
        return {"total": total, "page": page, "limit": limit,
                "pages": max(1, (total + limit - 1) // limit), "data": items}
    except Exception:
        app_logger.exception("Failed to list client job requests")
        raise AppException("Failed to fetch job requests", status_code=500)


async def list_open_job_requests(
    category_id: Optional[str],
    city: Optional[str],
    page: int,
    limit: int,
) -> dict:
    """Open job requests visible to providers for browsing."""
    try:
        skip  = (page - 1) * limit
        query = [
            JobRequest.job_status == JobRequestStatus.OPEN,
            JobRequest.is_deleted == False,
        ]
        if category_id:
            query.append(JobRequest.category_id == category_id)

        total = await JobRequest.find(*query).count()
        items = (
            await JobRequest.find(*query)
            .sort("-created_at").skip(skip).limit(limit).to_list()
        )
        # Strip location from all items in public listing
        for item in items:
            item.location = None
        return {"total": total, "page": page, "limit": limit,
                "pages": max(1, (total + limit - 1) // limit), "data": items}
    except Exception:
        app_logger.exception("Failed to list open job requests")
        raise AppException("Failed to fetch job requests", status_code=500)


async def list_job_applications(
    job_id: str,
    caller: User,
    page: int,
    limit: int,
) -> dict:
    """Applications for a job — client sees all, provider sees only their own."""
    try:
        if not ObjectId.is_valid(job_id):
            raise ValidationException("Invalid job request id")

        skip  = (page - 1) * limit
        query = [
            JobApplication.job_request_id == job_id,
            JobApplication.is_deleted     == False,
        ]
        if caller.user_type == UserRole.PROVIDER:
            query.append(JobApplication.provider_id == str(caller.id))

        total = await JobApplication.find(*query).count()
        items = (
            await JobApplication.find(*query)
            .sort("-created_at").skip(skip).limit(limit).to_list()
        )
        return {"total": total, "page": page, "limit": limit,
                "pages": max(1, (total + limit - 1) // limit), "data": items}
    except AppException:
        raise
    except Exception:
        app_logger.exception("Failed to list applications job_id=%s", job_id)
        raise AppException("Failed to fetch applications", status_code=500)