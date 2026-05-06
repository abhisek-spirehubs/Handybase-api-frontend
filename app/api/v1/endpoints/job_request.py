from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, status

from app.dependencies.auth import get_current_user
from app.dependencies.subscription import require_feature
from app.models.job_request import JobApplication, JobRequestStatus
from app.models.user import User, UserRole
from app.schemas.job_request import (
    JobApplicationCreate,
    JobApplicationDataResponse,
    JobRequestCreate,
    JobRequestDataResponse,
    JobRequestUpdate,
    SelectProviderRequest,
)
from app.schemas.common import APIResponse, PaginatedResponse, MessageResponse
from app.services import job_request as job_request
from app.core.exceptions import ForbiddenException

router = APIRouter(tags=["Job Post"])


# ═══════════════════════════════════════════════════════════════════════
# STATIC ROUTES FIRST
# ═══════════════════════════════════════════════════════════════════════

# ── Provider — browse open jobs ───────────────────────────────────────

@router.get(
    "/open",
    response_model=PaginatedResponse[JobRequestDataResponse],
)
async def browse_open_jobs(
    category_id: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type not in [UserRole.PROVIDER, UserRole.ADMIN]:
        raise ForbiddenException("Only providers can browse job requests.")

    result = await job_request.list_open_job_requests(
        category_id=category_id,
        city=city,
        page=page,
        limit=limit,
    )

    return PaginatedResponse(
        message="Open job requests fetched successfully",
        total=result["total"],
        data=result["data"],
    )


# ── Provider — list own applications ─────────────────────────────────

@router.get(
    "/my-applications",
    response_model=PaginatedResponse[JobApplicationDataResponse],
)
async def list_my_applications(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type != UserRole.PROVIDER:
        raise ForbiddenException("Only providers can access this.")

    skip = (page - 1) * limit

    total = await JobApplication.find(
        JobApplication.provider_id == str(current_user.id),
        JobApplication.is_deleted == False,
    ).count()

    items = (
        await JobApplication.find(
            JobApplication.provider_id == str(current_user.id),
            JobApplication.is_deleted == False,
        )
        .sort("-created_at")
        .skip(skip)
        .limit(limit)
        .to_list()
    )

    return PaginatedResponse(
        message="Applications fetched successfully",
        total=total,
        data=items,
    )


# ── Client — list own job requests ───────────────────────────────────

@router.get(
    "/my",
    response_model=PaginatedResponse[JobRequestDataResponse],
)
async def list_my_job_requests(
    status_filter: Optional[JobRequestStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type != UserRole.CLIENT:
        raise ForbiddenException("Only clients can access this.")

    result = await job_request.list_client_job_requests(
        client_id=str(current_user.id),
        status=status_filter,
        page=page,
        limit=limit,
    )

    return PaginatedResponse(
        message="Job requests fetched successfully",
        total=result["total"],
        data=result["data"],
    )


# ── Provider — withdraw application ─────────────────────────────────

@router.delete(
    "/applications/{application_id}",
    response_model=MessageResponse,
)
async def withdraw_application(
    application_id: str = Path(...),
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type != UserRole.PROVIDER:
        raise ForbiddenException("Only providers can withdraw applications.")

    await job_request.withdraw_application(
        provider=current_user,
        application_id=application_id,
    )

    return MessageResponse(message="Application withdrawn successfully")


# ═══════════════════════════════════════════════════════════════════════
# DYNAMIC ROUTES
# ═══════════════════════════════════════════════════════════════════════

# ── Client — post a job ───────────────────────────────────────────────

@router.post(
    "/",
    response_model=APIResponse[JobRequestDataResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_job_request(
    data: JobRequestCreate,
    current_user: User = Depends(require_feature("can_request_quotes")),
):
    if current_user.user_type != UserRole.CLIENT:
        raise ForbiddenException("Only clients can post job requests.")

    job = await job_request.create_job_request(
        client=current_user,
        data=data,
    )

    return APIResponse(
        message="Job request posted successfully",
        data=job,
    )


# ── Client — get single ──────────────────────────────────────────────

@router.get(
    "/{job_id}",
    response_model=APIResponse[JobRequestDataResponse],
)
async def get_job_request(
    job_id: str = Path(...),
    current_user: User = Depends(get_current_user),
):
    result = await job_request.get_job_request(
        caller=current_user,
        job_id=job_id,
    )

    job = result["job"]

    if not result["show_location"]:
        job.location = None

    return APIResponse(
        message="Job request fetched successfully",
        data=job,
    )


# ── Client — update ─────────────────────────────────────────────────

@router.put(
    "/{job_id}",
    response_model=APIResponse[JobRequestDataResponse],
)
async def update_job_request(
    job_id: str,
    data: JobRequestUpdate,
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type != UserRole.CLIENT:
        raise ForbiddenException("Only clients can update job requests.")

    job = await job_request.update_job_request(
        client=current_user,
        job_id=job_id,
        data=data,
    )

    return APIResponse(
        message="Job request updated successfully",
        data=job,
    )


# ── Client — cancel ────────────────────────────────────────────────

@router.post(
    "/{job_id}/cancel",
    response_model=APIResponse[JobRequestDataResponse],
)
async def cancel_job_request(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type != UserRole.CLIENT:
        raise ForbiddenException("Only clients can cancel job requests.")

    job = await job_request.cancel_job_request(
        client=current_user,
        job_id=job_id,
    )

    return APIResponse(
        message="Job request cancelled successfully",
        data=job,
    )


# ── Client — select provider ───────────────────────────────────────

@router.post(
    "/{job_id}/select-applicants",
    response_model=APIResponse[JobRequestDataResponse],
)
async def select_provider(
    job_id: str,
    data: SelectProviderRequest,
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type != UserRole.CLIENT:
        raise ForbiddenException("Only clients can select providers.")

    job = await job_request.select_provider(
        client=current_user,
        job_id=job_id,
        data=data,
    )

    return APIResponse(
        message="Provider selected and booking created successfully",
        data=job,
    )


# ── Applications list ───────────────────────────────────────────────

@router.get(
    "/{job_id}/applications",
    response_model=PaginatedResponse[JobApplicationDataResponse],
)
async def list_applications(
    job_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    result = await job_request.list_job_applications(
        job_id=job_id,
        caller=current_user,
        page=page,
        limit=limit,
    )

    return PaginatedResponse(
        message="Applications fetched successfully",
        total=result["total"],
        data=result["data"],
    )


# ── Provider — apply ───────────────────────────────────────────────

@router.post(
    "/{job_id}/apply",
    response_model=APIResponse[JobApplicationDataResponse],
    status_code=status.HTTP_201_CREATED,
)
async def apply_to_job(
    job_id: str,
    data: JobApplicationCreate,
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type != UserRole.PROVIDER:
        raise ForbiddenException("Only providers can apply to job requests.")

    application = await job_request.apply_to_job(
        provider=current_user,
        job_id=job_id,
        data=data,
    )

    return APIResponse(
        message="Application submitted successfully",
        data=application,
    )