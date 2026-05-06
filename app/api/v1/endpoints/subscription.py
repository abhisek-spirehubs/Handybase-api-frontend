from fastapi import APIRouter, Depends, Query, BackgroundTasks
from typing import Optional

from app.dependencies.auth import get_current_user, admin_required
from app.models.user import User, UserRole
from app.models.subscription import SubscriptionStatus

from app.schemas.subscription import (
    SubscribeRequest,
    UpgradeRequest,
    RenewRequest,
    CancelSubscriptionRequest,
    SubscriptionDataResponse,
    MySubscriptionDataResponse,
)

from app.schemas.common import (
    APIResponse,
    PaginatedResponse,
    MessageResponse,
)

from app.services.subscription_service import SubscriptionService


router = APIRouter()


# ─────────────────────────────────────────
# GET CURRENT SUBSCRIPTION
# ─────────────────────────────────────────

@router.get(
    "/current",
    response_model=APIResponse[MySubscriptionDataResponse],
)
async def get_current_subscription(
    current_user: User = Depends(get_current_user),
):
    data = await SubscriptionService.get_current_subscription_response(
        user_id=str(current_user.id),
        user_type=current_user.user_type,
    )

    return {
        "success": True,
        "message": "Subscription fetched successfully",
        "data": data,
    }


# ─────────────────────────────────────────
# GET SUBSCRIPTION HISTORY
# ─────────────────────────────────────────

@router.get(
    "/history",
    response_model=PaginatedResponse[SubscriptionDataResponse],
    summary="Get my subscription history",
)
async def get_subscription_history(
    current_user: User = Depends(get_current_user),
):
    history = await SubscriptionService.get_subscription_history(
        str(current_user.id),
        current_user.user_type,
    )

    return {
        "success": True,
        "message": "Subscription history fetched successfully",
        "total": len(history),
        "data": history,
    }


# ─────────────────────────────────────────
# SUBSCRIBE
# ─────────────────────────────────────────

@router.post(
    "/subscribe",
    response_model=APIResponse[SubscriptionDataResponse],
    summary="Subscribe to a plan",
)
async def subscribe(
    data: SubscribeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    sub = await SubscriptionService.subscribe(
        user_id=str(current_user.id),
        plan_id=data.plan_id,
        background_tasks=background_tasks,
        payment_id=data.payment_id,
        amount_paid=data.amount_paid,
        currency=data.currency,
    )

    return {
        "success": True,
        "message": "Subscription activated successfully",
        "data": sub,
    }


# ─────────────────────────────────────────
# UPGRADE
# ─────────────────────────────────────────

@router.post(
    "/upgrade",
    response_model=APIResponse[SubscriptionDataResponse],
    summary="Upgrade to a higher plan",
)
async def upgrade_subscription(
    data: UpgradeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    sub = await SubscriptionService.upgrade_subscription(
        user_id=str(current_user.id),
        new_plan_id=data.plan_id,
        background_tasks=background_tasks,
        payment_id=data.payment_id,
        amount_paid=data.amount_paid,
        currency=data.currency,
    )

    return {
        "success": True,
        "message": "Plan upgraded successfully",
        "data": sub,
    }


# ─────────────────────────────────────────
# RENEW
# ─────────────────────────────────────────

@router.post(
    "/renew",
    response_model=APIResponse[SubscriptionDataResponse],
    summary="Renew current plan",
)
async def renew_subscription(
    data: RenewRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    sub = await SubscriptionService.renew_subscription(
        user_id=str(current_user.id),
        background_tasks=background_tasks,
        payment_id=data.payment_id,
        amount_paid=data.amount_paid,
        currency=data.currency,
    )

    return {
        "success": True,
        "message": "Subscription renewed successfully",
        "data": sub,
    }


# ─────────────────────────────────────────
# CANCEL
# ─────────────────────────────────────────

@router.post(
    "/cancel",
    response_model=MessageResponse,
    summary="Cancel active subscription",
)
async def cancel_subscription(
    data: CancelSubscriptionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    return await SubscriptionService.cancel_subscription(
        user_id=str(current_user.id),
        background_tasks=background_tasks,
        reason=data.reason,
    )


# ─────────────────────────────────────────
# LIST (ADMIN + USER)
# ─────────────────────────────────────────

@router.get(
    "",
    response_model=PaginatedResponse[SubscriptionDataResponse],
    summary="List subscriptions",
)
async def list_subscriptions(
    status: Optional[SubscriptionStatus] = Query(None),
    plan_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type == UserRole.ADMIN:
        subs = await SubscriptionService.get_all_subscriptions(
            status=status.value if status else None,
            plan_type=plan_type,
        )

        return {
            "success": True,
            "message": "All subscriptions fetched successfully",
            "total": len(subs),
            "data": subs,
        }

    subs = await SubscriptionService.get_subscription_history(
        str(current_user.id),
        current_user.user_type,
    )

    return {
        "success": True,
        "message": "Subscriptions fetched successfully",
        "total": len(subs),
        "data": subs,
    }


# ─────────────────────────────────────────
# ADMIN EXPIRE TRIGGER
# ─────────────────────────────────────────

@router.post(
    "/expire",
    response_model=MessageResponse,
    summary="[ADMIN] Trigger expiry job",
)
async def trigger_expiry(
    _: User = Depends(admin_required),
):
    count = await SubscriptionService.expire_stale_subscriptions()

    return {
        "success": True,
        "message": f"Expired {count} subscription(s)",
    }