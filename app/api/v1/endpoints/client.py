from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from typing import Optional

from app.dependencies.auth import admin_required, client_or_admin_required
from app.dependencies.rate_limit import register_rate_limit
from app.models.user import User, UserRole
from app.schemas.client import ClientDataResponse, ClientRegister, ClientStatusUpdate
from app.schemas.common import APIResponse, PaginatedResponse, MessageResponse
from app.services.client_service import UserService

router = APIRouter()


# ── Registration ───────────────────────────────────────────────────────────────
@router.post(
    "",
    response_model=APIResponse[ClientDataResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register new client",
)
@register_rate_limit()
async def register_client(request: Request, data: ClientRegister):
    """Public — register a new client account."""
    client = await UserService.register_client(data)

    return {
        "success": True,
        "message": "Account created successfully",
        "data":    client,
    }


# ── Get profile ────────────────────────────────────────────────────────────────
@router.get(
    "/profile",
    response_model=APIResponse[ClientDataResponse],
    summary="Get own profile (client) or any client profile by ID (admin)",
)
async def get_profile(
    client_id:    Optional[str] = Query(None, description="[ADMIN] Target client ID"),
    current_user: User          = Depends(client_or_admin_required),
):
    """
    Client → returns own profile (client_id ignored).
    Admin  → pass client_id to fetch any client's profile.
    """
    if current_user.user_type == UserRole.ADMIN and client_id:
        client = await UserService.get_client_by_id(client_id)
    else:
        client = await UserService.get_me(current_user)

    return {
        "success": True,
        "message": "Profile fetched successfully",
        "data":    client,
    }


# ── Update profile ─────────────────────────────────────────────────────────────
@router.put(
    "/update",
    response_model=APIResponse[ClientDataResponse],
    summary="Update own profile (client) or any client profile by ID (admin)",
)
async def update_profile(
    client_id:     Optional[str]        = Form(None, description="[ADMIN] Target client ID"),
    fname:         Optional[str]        = Form(None),
    lname:         Optional[str]        = Form(None),
    phone:         Optional[str]        = Form(None),
    date_of_birth: Optional[str]        = Form(None, description="ISO format: YYYY-MM-DD"),
    avatar:        Optional[UploadFile] = File(None),
    current_user:  User                 = Depends(client_or_admin_required),
):
    """
    Client → updates own profile (client_id ignored).
    Admin  → pass client_id to update any client's profile.
    """
    target_id = (
        client_id
        if current_user.user_type == UserRole.ADMIN and client_id
        else str(current_user.id)
    )

    client = await UserService.update_client_profile(
        user_id=target_id,
        fname=fname,
        lname=lname,
        phone=phone,
        date_of_birth=date_of_birth,
        avatar=avatar,
    )

    return {
        "success": True,
        "message": "Profile updated successfully",
        "data":    client,
    }


# ── Admin — list ───────────────────────────────────────────────────────────────
@router.get(
    "",
    response_model=PaginatedResponse[ClientDataResponse],
    summary="[ADMIN] List all clients",
)
async def list_clients(
    page:         int           = Query(1, ge=1),
    limit:        int           = Query(10, ge=1, le=100),
    search:       Optional[str] = Query(None, description="Search by name or email"),
    status:       Optional[str] = Query(None, description="Filter by status: active | inactive"),
    _:            User          = Depends(admin_required),
):
    # Service returns PaginatedResponse-shaped dict — return directly
    return await UserService.get_all_clients(page, limit, search, status)


# ── Admin — status ─────────────────────────────────────────────────────────────
@router.patch(
    "/{client_id}/status",
    response_model=MessageResponse,
    summary="[ADMIN] Activate or suspend a client",
)
async def update_client_status(
    client_id: str,
    data:      ClientStatusUpdate,
    admin:     User = Depends(admin_required),
):
    # Service returns MessageResponse-shaped dict — return directly
    return await UserService.update_client_status(
        client_id,
        data.status,
        str(admin.id),
    )


# ── Admin — delete ─────────────────────────────────────────────────────────────
@router.delete(
    "/{client_id}",
    response_model=MessageResponse,
    summary="[ADMIN] Soft-delete a client",
)
async def delete_client(
    client_id: str,
    admin:     User = Depends(admin_required),
):
    # Service returns MessageResponse-shaped dict — return directly
    return await UserService.delete_client(
        client_id,
        str(admin.id),
    )