from fastapi import APIRouter, Depends
from app.dependencies.auth import admin_required
from app.services.admin_service import AdminService
from app.schemas.common import APIResponse
from fastapi import APIRouter, Depends
from app.dependencies.auth import admin_required
from app.models.user import User
from app.services.subscription_service import SubscriptionService
from app.schemas.common import MessageResponse


router = APIRouter(dependencies=[Depends(admin_required)])


@router.get(
    "/dashboard",
    summary="[ADMIN] Platform activity summary",
)
async def get_dashboard():
    """
    Returns platform-wide stats:
    - Total users (clients + providers)
    - Total bookings by status
    - Revenue summary
    - Pending provider approvals
    - Pending service approvals
    """
    return await AdminService.get_dashboard_stats()



@router.post("/subscriptions/expire", response_model=MessageResponse)
async def manual_expire_subscriptions(
    current_admin: User = Depends(admin_required)
):
    count = await SubscriptionService.expire_stale_subscriptions()
    return {"success": True, "message": f"Expired {count} subscriptions"}

@router.post("/subscriptions/warn", response_model=MessageResponse)
async def manual_warn_expiring_subscriptions(
    current_admin: User = Depends(admin_required)
):
    count = await SubscriptionService.warn_expiring_subscriptions()
    return {"success": True, "message": f"Sent warnings to {count} users"}