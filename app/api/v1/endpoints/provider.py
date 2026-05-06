import json
from typing import Optional

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form,
    Query, Request, UploadFile, status,
)

from app.services.provider_service import ProviderService
from app.schemas.provider import (
    ProviderApprovalRequest,
    ProviderStatusFilter,
    PublicProviderResponse,
    AdminProviderResponse,
)
from app.schemas.common import APIResponse, PaginatedResponse, MessageResponse
from app.dependencies.auth import (
    admin_required,
    admin_or_provider_required,
    get_current_user,
)
from app.models.user import User, UserRole
from app.dependencies.rate_limit import register_rate_limit
from app.core.exceptions import ValidationException

router = APIRouter()


# ── Registration ───────────────────────────────────────────────────────────────
@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register as a new provider — submitted for admin approval",
)
@register_rate_limit()
async def provider_register(
    request:          Request,
    background_tasks: BackgroundTasks,
    email:            str           = Form(...),
    password:         str           = Form(..., min_length=8),
    business_name:    str           = Form(...),
    fname:            Optional[str] = Form(None),
    lname:            Optional[str] = Form(None),
    phone:            Optional[str] = Form(None),
    bio:              Optional[str] = Form(None),
    services:         Optional[str] = Form(None),
    profile_image:    Optional[UploadFile] = File(None),
    portfolio_image:  Optional[UploadFile] = File(None),
):
    """Public — submit provider registration for admin approval."""
    # Service returns MessageResponse-shaped dict — return directly
    return await ProviderService.register_provider(
        email=email,
        password=password,
        business_name=business_name,
        background_tasks=background_tasks,
        fname=fname,
        lname=lname,
        phone=phone,
        bio=bio,
        services=services,
        profile_image=profile_image,
        portfolio_image=portfolio_image,
    )


# ── Public list ────────────────────────────────────────────────────────────────
@router.get(
    "",
    response_model=PaginatedResponse[PublicProviderResponse],
    summary="List approved providers (public)",
)
async def get_providers(
    page:         int           = Query(1, ge=1),
    limit:        int           = Query(10, ge=1, le=100),
    service:      Optional[str] = Query(None),
    search:       Optional[str] = Query(None, max_length=100),
    current_user: Optional[User] = Depends(get_current_user),
):
    result = await ProviderService.get_providers(
        page=page,
        limit=limit,
        service=service,
        search=search,
        current_user=current_user,
        is_admin=False,
    )

    return {
        "success": result["success"],
        "message": result["message"],
        "total":   result["total"],
        "data": [
            PublicProviderResponse.model_validate(item, from_attributes=True)
            for item in result["data"]
        ],
    }


# ── Admin list ─────────────────────────────────────────────────────────────────
@router.get(
    "/admin",
    response_model=PaginatedResponse[AdminProviderResponse],
    summary="[ADMIN] List all providers with filters",
)
async def get_providers_admin(
    page:   int                            = Query(1, ge=1),
    limit:  int                            = Query(10, ge=1, le=100),
    status: Optional[ProviderStatusFilter] = Query(None),
    search: Optional[str]                  = Query(None, max_length=100),
    _:      User                           = Depends(admin_required),
):
    result = await ProviderService.get_providers(
        page=page,
        limit=limit,
        status_filter=status.value if status else None,
        search=search,
        is_admin=True,
        current_user=None,
    )

    return {
        "success": result["success"],
        "message": result["message"],
        "total":   result["total"],
        "data": [
            AdminProviderResponse.model_validate(doc, from_attributes=True)
            for doc in result["data"]
        ],
    }


# ── Get own profile (or any provider by ID for admin) ─────────────────────────
@router.get(
    "/me",
    response_model=APIResponse[AdminProviderResponse],
    summary="Get own profile (provider) or any provider by ID (admin)",
)
async def get_profile(
    provider_id:  Optional[str] = Query(None, description="[ADMIN] Target provider ID"),
    current_user: User          = Depends(admin_or_provider_required),
):
    target_id = (
        provider_id
        if current_user.user_type == UserRole.ADMIN and provider_id
        else str(current_user.id)
    )
    provider = await ProviderService.get_provider(
        provider_id=target_id,
        is_admin=True,
    )

    return {
        "success": True,
        "message": "Profile fetched successfully",
        "data":    AdminProviderResponse.model_validate(provider, from_attributes=True),
    }


# ── Update profile ─────────────────────────────────────────────────────────────
@router.put(
    "/update",
    response_model=MessageResponse,
    summary="Update own profile (provider) or any provider by ID (admin)",
)
async def update_profile(
    provider_id:     Optional[str]        = Form(None),
    business_name:   Optional[str]        = Form(None),
    description:     Optional[str]        = Form(None),
    phone:           Optional[str]        = Form(None),
    services:        Optional[str]        = Form(None),
    website_url:     Optional[str]        = Form(None, max_length=500),
    social_links:    Optional[str]        = Form(None),
    profile_image:   Optional[UploadFile] = File(None),
    portfolio_image: Optional[UploadFile] = File(None),
    current_user:    User                 = Depends(admin_or_provider_required),
):
    target_id = (
        provider_id
        if current_user.user_type == UserRole.ADMIN and provider_id
        else str(current_user.id)
    )

    parsed_social_links = None
    if social_links is not None:
        try:
            parsed_social_links = json.loads(social_links)
            if not isinstance(parsed_social_links, dict):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            raise ValidationException(
                'social_links must be a valid JSON object '
                'e.g. {"instagram": "https://...", "facebook": "https://..."}'
            )

    # Service returns MessageResponse-shaped dict — return directly
    return await ProviderService.update_provider_profile(
        provider_id=target_id,
        business_name=business_name,
        description=description,
        phone=phone,
        services=services,
        website_url=website_url,
        social_links=parsed_social_links,
        profile_image=profile_image,
        portfolio_image=portfolio_image,
    )


# ── Public single provider ─────────────────────────────────────────────────────
@router.get(
    "/{provider_id}",
    response_model=APIResponse[PublicProviderResponse],
    summary="Get provider by ID (public)",
)
async def get_provider(
    provider_id:      str,
    background_tasks: BackgroundTasks,
    current_user:     Optional[User] = Depends(get_current_user),
):
    provider = await ProviderService.get_provider_detail(
        provider_id=provider_id,
        current_user=current_user,
    )

    from app.services.analytics_service import record_profile_visit
    background_tasks.add_task(
        record_profile_visit,
        provider_id=provider_id,
        visit_type="profile",
        visitor_user_id=str(current_user.id) if current_user else None,
    )

    # Build the response — mask contact fields for non-paid users
    data = PublicProviderResponse.model_validate(provider, from_attributes=True)
    if not getattr(provider, "_expose_contact", False):
        data.phone = None
        data.email = None

    return {
        "success": True,
        "message": "Provider fetched successfully",
        "data":    data,
    }


# ── Admin — approve/reject ─────────────────────────────────────────────────────
@router.patch(
    "/{provider_id}/status",
    response_model=MessageResponse,
    summary="[ADMIN] Approve or reject a provider",
)
async def update_provider_status(
    provider_id:      str,
    data:             ProviderApprovalRequest,
    background_tasks: BackgroundTasks,
    current_admin:    User = Depends(admin_required),
):
    # Service returns MessageResponse-shaped dict — return directly
    return await ProviderService.update_approval(
        provider_id=provider_id,
        action=data.action,
        reason=data.reason,
        admin_id=str(current_admin.id),
        background_tasks=background_tasks,
    )


# ── Admin — delete ─────────────────────────────────────────────────────────────
@router.delete(
    "/{provider_id}",
    response_model=MessageResponse,
    summary="[ADMIN] Soft-delete a provider",
)
async def delete_provider(
    provider_id:      str,
    background_tasks: BackgroundTasks,
    current_admin:    User = Depends(admin_required),
):
    # Service returns MessageResponse-shaped dict — return directly
    return await ProviderService.delete_provider(
        provider_id=provider_id,
        admin_id=str(current_admin.id),
        background_tasks=background_tasks,
    )


# ── Admin — restore ────────────────────────────────────────────────────────────
@router.post(
    "/{provider_id}/restore",
    response_model=MessageResponse,
    summary="[ADMIN] Restore a soft-deleted provider",
)
async def restore_provider(
    provider_id:      str,
    background_tasks: BackgroundTasks,
    current_admin:    User = Depends(admin_required),
):
    # Service returns MessageResponse-shaped dict — return directly
    return await ProviderService.restore_provider(
        provider_id=provider_id,
        admin_id=str(current_admin.id),
        background_tasks=background_tasks,
    )