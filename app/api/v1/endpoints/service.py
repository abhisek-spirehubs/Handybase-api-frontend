from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, BackgroundTasks, status
from typing import Optional

from app.services.service_service import ServiceService
from app.dependencies.auth import get_current_user, admin_required
from app.models.user import User, UserRole
from app.schemas.service import (
    ServiceResponse,
    PublicServiceResponse,
    ServiceApprovalRequest,
)
from app.schemas.common import APIResponse, MessageResponse, PaginatedResponse
from app.dependencies.subscription import require_feature

router = APIRouter()


# ─────────────────────────────────────────────
# GET /services
# ─────────────────────────────────────────────
@router.get(
    "",
    response_model=PaginatedResponse[ServiceResponse],
    summary="Get services list",
)
async def get_services(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=100),
    category_id: Optional[str] = Query(None),
    city: Optional[str] = Query(None, max_length=100),
    state: Optional[str] = Query(None, max_length=100),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    sort_by: str = Query("newest", pattern="^(newest|oldest|price_low|price_high)$"),
    approval_status: Optional[str] = Query(None),
    provider_id: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user),
):
    result = await ServiceService.get_services(
        current_user=current_user,
        page=page,
        limit=limit,
        approval_status=approval_status,
        provider_id=provider_id,
        category_id=category_id,
        search=search,
        city=city,
        state=state,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
    )

    is_internal = current_user and current_user.user_type in [UserRole.ADMIN, UserRole.PROVIDER]
    schema = ServiceResponse if is_internal else PublicServiceResponse

    items = [
        schema.model_validate(doc, from_attributes=True)
        for doc in result["data"]
    ]

    return PaginatedResponse(
        success=True,
        message="Services retrieved successfully",
        total=result["total"],
        data=items,
    )


# ─────────────────────────────────────────────
# GET SINGLE
# ─────────────────────────────────────────────
@router.get(
    "/{service_id}",
    response_model=APIResponse[ServiceResponse],
)
async def get_service(
    service_id: str,
    background_tasks: BackgroundTasks,
    current_user: Optional[User] = Depends(get_current_user),
):
    service = await ServiceService.get_by_id(service_id)

    return APIResponse(
        success=True,
        message="Service retrieved successfully",
        data=ServiceResponse.model_validate(service, from_attributes=True),
    )


# ─────────────────────────────────────────────
# CREATE
# ─────────────────────────────────────────────
@router.post(
    "",
    response_model=APIResponse[ServiceResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_service(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    category_id: str = Form(...),
    price: float = Form(...),
    duration: int = Form(...),
    city: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_feature("can_list_services")),
):
    service = await ServiceService.create_service(
        provider_id=str(current_user.id),
        title=title,
        description=description,
        category_id=category_id,
        price=price,
        duration=duration,
        city=city,
        state=state,
        image=image,
    )

    return APIResponse(
        message="Service created successfully",
        data=ServiceResponse.model_validate(service, from_attributes=True),
    )


# ─────────────────────────────────────────────
# UPDATE
# ─────────────────────────────────────────────
@router.put(
    "/{service_id}",
    response_model=APIResponse[ServiceResponse],
)
async def update_service(
    service_id: str,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    category_id: str = Form(...),
    price: float = Form(...),
    duration: int = Form(...),
    city: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
):
    service = await ServiceService.update_service(
        service_id=service_id,
        user=current_user,
        title=title,
        description=description,
        category_id=category_id,
        price=price,
        duration=duration,
        city=city,
        state=state,
        image=image,
    )

    return APIResponse(
        message="Service updated successfully",
        data=ServiceResponse.model_validate(service, from_attributes=True),
    )


# ─────────────────────────────────────────────
# DELETE
# ─────────────────────────────────────────────
@router.delete(
    "/{service_id}",
    response_model=MessageResponse,
)
async def delete_service(
    service_id: str,
    current_user: User = Depends(get_current_user),
):
    await ServiceService.delete_service(service_id, current_user)

    return MessageResponse(
        message="Service deleted successfully"
    )


# ─────────────────────────────────────────────
# APPROVAL
# ─────────────────────────────────────────────
@router.patch(
    "/{service_id}/status",
    response_model=APIResponse[ServiceResponse],
)
async def update_service_status(
    service_id: str,
    data: ServiceApprovalRequest,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(admin_required),
):
    service = await ServiceService.update_service_approval(
        service_id=service_id,
        action=data.action,
        reason=data.reason,
        admin_id=str(current_admin.id),
        background_tasks=background_tasks,
    )

    return APIResponse(
        message=(
            "Service approved successfully"
            if data.action == "approve"
            else "Service rejected successfully"
        ),
        data=ServiceResponse.model_validate(service, from_attributes=True),
    )
