from fastapi import Depends
from app.dependencies.auth import get_current_user
from app.models.user import User, UserRole
from app.core.exceptions import ForbiddenException


def require_feature(feature: str):
    """
    Route dependency — gates access behind a subscription feature.

    Usage:
        @router.post("/bookings/")
        async def create_booking(
            current_user: User = Depends(require_feature("can_book"))
        ):

    Admin always bypasses feature gates.
    Returns the current_user so routes can still use it.
    """
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        # Admin always passes — no subscription needed
        if current_user.user_type == UserRole.ADMIN:
            return current_user

        # Local import — avoids circular import at module load time
        from app.services.subscription_service import SubscriptionService

        features = await SubscriptionService.get_user_features(
            str(current_user.id),
            current_user.user_type,
        )

        if not getattr(features, feature, False):
            raise ForbiddenException(
                "Your current plan does not include this feature. Please upgrade."
            )

        return current_user

    return checker
# ```

# ---

# ## Summary of the full flow for Tier 1 provider creating a service
# ```
# POST /services/
#   ↓
# require_feature("can_list_services")
#   → checks Tier 1 features
#   → can_list_services = True  ✅ PASSES
#   ↓
# create_service() in service_service.py
#   → subscription gate block
#   → can_list_services = True  ✅ PASSES
#   → max_services = 3
#   → counts existing services
#   → if count < 3 → ALLOWED ✅
#   → if count >= 3 → 403 "You have reached the maximum of 3 services" ❌