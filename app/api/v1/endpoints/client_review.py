from fastapi import APIRouter, Depends, Path, Query, status

from app.dependencies.auth import get_current_user
from app.dependencies.subscription import require_feature
from app.models.user import User, UserRole
from app.schemas.client_rating import (
    ClientReviewCreate,
    ClientReviewUpdate,
    ClientReviewResponse,
)
from app.schemas.common import APIResponse, PaginatedResponse, MessageResponse
from app.services import client_review
from app.core.exceptions import ForbiddenException

router = APIRouter()


# ── CREATE ─────────────────────────────────────────

@router.post(
    "",
    response_model=APIResponse[ClientReviewResponse],
    status_code=status.HTTP_201_CREATED,
)
async def rate_client(
    data: ClientReviewCreate,
    current_user: User = Depends(require_feature("can_rate_clients")),
):
    if current_user.user_type != UserRole.PROVIDER:
        raise ForbiddenException("Only providers can rate clients.")

    review = await client_review.create_client_review(
        provider=current_user,
        data=data,
    )

    return APIResponse(
        message="Client rated successfully",
        data=review,
    )


# ── PROVIDER REVIEWS ───────────────────────────────

@router.get(
    "",
    response_model=PaginatedResponse[ClientReviewResponse],
)
async def get_my_client_reviews(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type != UserRole.PROVIDER:
        raise ForbiddenException("Only providers can access this endpoint.")

    result = await client_review.get_reviews_by_provider(
        provider_id=str(current_user.id),
        page=page,
        limit=limit,
    )

    return PaginatedResponse(
        message="Reviews fetched successfully",
        total=result["total"],
        data=result["reviews"],
    )


# ── CLIENT REVIEWS ────────────────────────────────

@router.get(
    "/{client_id}",
    response_model=PaginatedResponse[ClientReviewResponse],
)
async def get_client_ratings(
    client_id: str = Path(...),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    from app.services.subscription_service import SubscriptionService

    if current_user.user_type == UserRole.CLIENT:
        if str(current_user.id) != client_id:
            raise ForbiddenException("You can only view your own reviews.")

        features = await SubscriptionService.get_user_features(
            str(current_user.id),
            UserRole.CLIENT,
        )

        if not getattr(features, "can_leave_reviews", False):
            raise ForbiddenException("Upgrade required to view reviews.")

    elif current_user.user_type == UserRole.PROVIDER:
        features = await SubscriptionService.get_user_features(
            str(current_user.id),
            UserRole.PROVIDER,
        )

        if not getattr(features, "can_rate_clients", False):
            raise ForbiddenException("Upgrade to Tier 3 required.")

    elif current_user.user_type != UserRole.ADMIN:
        raise ForbiddenException("Not allowed.")

    result = await client_review.get_reviews_for_client(
        client_id=client_id,
        page=page,
        limit=limit,
    )

    return PaginatedResponse(
        message="Client ratings fetched successfully",
        total=result["total"],
        data=result["reviews"],
    )


# ── DELETE ─────────────────────────────────────────

@router.delete(
    "/{review_id}",
    response_model=MessageResponse,
)
async def delete_client_review(
    review_id: str,
    current_user: User = Depends(get_current_user),
):
    await client_review.delete_client_review(
        user=current_user,
        review_id=review_id,
    )

    return MessageResponse(message="Review deleted successfully")


# ── UPDATE ─────────────────────────────────────────

@router.put(
    "/{review_id}",
    response_model=APIResponse[ClientReviewResponse],
)
async def update_client_review(
    review_id: str,
    data: ClientReviewUpdate,
    current_user: User = Depends(get_current_user),
):
    review = await client_review.update_client_review(
        user=current_user,
        review_id=review_id,
        rating=data.rating,
        comment=data.comment,
    )

    return APIResponse(
        message="Review updated successfully",
        data=review,
    )