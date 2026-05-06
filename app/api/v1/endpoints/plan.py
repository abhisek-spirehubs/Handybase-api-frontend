from fastapi import Depends, Query, APIRouter
from typing import Optional

from app.dependencies.auth import get_current_user_optional, admin_required
from app.models.user import User, UserRole

from app.schemas.plan import (
    ClientPlanCreate,
    ClientPlanUpdate,
    ProviderPlanCreate,
    PlanResponse,
)

from app.schemas.common import (
    APIResponse,
    PaginatedResponse,
    MessageResponse,
)

from app.services.plan_service import PlanService

router = APIRouter()


# ─────────────────────────────────────────
# LIST PLANS
# ─────────────────────────────────────────
@router.get(
    "",
    response_model=PaginatedResponse[PlanResponse],
)
async def list_plans(
    user_type: Optional[str] = Query(None),
    plan_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    is_admin = (
        current_user is not None
        and current_user.user_type == UserRole.ADMIN
    )

    if user_type == "client":
        plans = await PlanService.get_client_plans(
            is_admin=is_admin,
            is_active=is_active if is_admin else None,
            plan_type=plan_type,
        )

    elif user_type == "provider":
        plans = await PlanService.get_provider_plans(
            is_admin=is_admin,
            is_active=is_active if is_admin else None,
            plan_type=plan_type,
        )

    else:
        client_plans = await PlanService.get_client_plans(
            is_admin=is_admin,
            is_active=is_active if is_admin else None,
            plan_type=plan_type,
        )
        provider_plans = await PlanService.get_provider_plans(
            is_admin=is_admin,
            is_active=is_active if is_admin else None,
            plan_type=plan_type,
        )
        plans = client_plans + provider_plans

    return {
        "success": True,
        "message": "Plans fetched successfully",
        "total": len(plans),
        "data": plans,
    }


# ─────────────────────────────────────────
# GET SINGLE PLAN
# ─────────────────────────────────────────
@router.get(
    "/{plan_id}",
    response_model=APIResponse[PlanResponse],
)
async def get_plan(plan_id: str):
    plan = await PlanService.get_plan_by_id(plan_id)

    return {
        "success": True,
        "message": "Plan fetched successfully",
        "data": plan,
    }


# ─────────────────────────────────────────
# CREATE CLIENT PLAN
# ─────────────────────────────────────────
@router.post(
    "/client",
    response_model=APIResponse[PlanResponse],
    status_code=201,
)
async def create_client_plan(
    data: ClientPlanCreate,
    current_admin: User = Depends(admin_required),
):
    plan = await PlanService.create_client_plan(
        data=data.model_dump(),
        admin_id=str(current_admin.id),
    )

    return {
        "success": True,
        "message": "Client plan created successfully",
        "data": plan,
    }


# ─────────────────────────────────────────
# CREATE PROVIDER PLAN
# ─────────────────────────────────────────
@router.post(
    "/provider",
    response_model=APIResponse[PlanResponse],
    status_code=201,
)
async def create_provider_plan(
    data: ProviderPlanCreate,
    current_admin: User = Depends(admin_required),
):
    plan = await PlanService.create_provider_plan(
        data=data.model_dump(),
        admin_id=str(current_admin.id),
    )

    return {
        "success": True,
        "message": "Provider plan created successfully",
        "data": plan,
    }


# ─────────────────────────────────────────
# UPDATE PLAN
# ─────────────────────────────────────────
@router.put(
    "/{plan_id}",
    response_model=APIResponse[PlanResponse],
)
async def update_plan(
    plan_id: str,
    data: ClientPlanUpdate,
    current_admin: User = Depends(admin_required),
):
    plan = await PlanService.update_plan(
        plan_id=plan_id,
        data=data.model_dump(exclude_none=True),
        admin_id=str(current_admin.id),
    )

    return {
        "success": True,
        "message": "Plan updated successfully",
        "data": plan,
    }


# ─────────────────────────────────────────
# DELETE PLAN
# ─────────────────────────────────────────
@router.delete(
    "/{plan_id}",
    response_model=MessageResponse,
)
async def delete_plan(
    plan_id: str,
    current_admin: User = Depends(admin_required),
):
    return await PlanService.delete_plan(
        plan_id=plan_id,
        admin_id=str(current_admin.id),
    )