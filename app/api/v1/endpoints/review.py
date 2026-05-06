from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from typing import List, Optional

from app.dependencies.auth import get_current_user, admin_required
from app.dependencies.subscription import require_feature
from app.models.user import User

from app.schemas.review import (
    ReviewResponse,
    ReviewModerationResponse,
)
from app.schemas.common import (
    APIResponse,
    MessageResponse,
    PaginatedResponse,
)

from app.services.review_service import ReviewService

router = APIRouter()


# ─────────────────────────────────────────────
# ADMIN — LIST ALL REVIEWS
# ─────────────────────────────────────────────
@router.get(
    "/all",
    response_model=PaginatedResponse[ReviewModerationResponse],
    summary="[ADMIN] List all reviews with filters",
)
async def get_all_reviews(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    provider_id: Optional[str] = Query(None),
    client_id: Optional[str] = Query(None),
    min_rating: Optional[float] = Query(None, ge=1, le=5),
    include_deleted: bool = Query(False),
    current_admin: User = Depends(admin_required),
):
    result = await ReviewService.get_all_reviews(
        page=page,
        limit=limit,
        provider_id=provider_id,
        client_id=client_id,
        min_rating=min_rating,
        include_deleted=include_deleted,
    )

    items = [
        ReviewModerationResponse.model_validate(r)
        for r in result["data"]
    ]

    return PaginatedResponse(
        success=True,
        message="Reviews retrieved successfully",
        total=result["total"],
        data=items,
    )


# ─────────────────────────────────────────────
# PUBLIC — PROVIDER REVIEWS
# ─────────────────────────────────────────────
@router.get(
    "/{provider_id}",
    response_model=PaginatedResponse[ReviewResponse],
    summary="Get reviews for a provider",
)
async def get_provider_reviews(
    provider_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    min_rating: Optional[float] = Query(None, ge=1, le=5),
):
    result = await ReviewService.get_provider_reviews(
        provider_id=provider_id,
        page=page,
        limit=limit,
        min_rating=min_rating,
    )

    items = [
        ReviewResponse.model_validate(r)
        for r in result["data"]
    ]

    return PaginatedResponse(
        success=True,
        message="Reviews retrieved successfully",
        total=result["total"],
        data=items,
    )


# ─────────────────────────────────────────────
# CREATE REVIEW
# ─────────────────────────────────────────────
@router.post(
    "/{booking_id}",
    response_model=APIResponse[ReviewResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Submit a review",
)
async def create_review(
    booking_id: str,
    rating: float = Form(..., ge=1, le=5),
    comment: Optional[str] = Form(None, max_length=1000),
    media_files: List[UploadFile] = File(default=[]),
    current_user: User = Depends(require_feature("can_leave_reviews")),
):
    review = await ReviewService.create_review(
        client_id=str(current_user.id),
        client_type=current_user.user_type,
        booking_id=booking_id,
        rating=rating,
        comment=comment,
        media_files=media_files if media_files else None,
    )

    return APIResponse(
        message="Review created successfully",
        data=ReviewResponse.model_validate(review, from_attributes=True),
    )


# ─────────────────────────────────────────────
# UPDATE REVIEW
# ─────────────────────────────────────────────
@router.put(
    "/{review_id}",
    response_model=APIResponse[ReviewResponse],
    summary="Update review",
)
async def update_review(
    review_id: str,
    rating: Optional[float] = Form(None, ge=1, le=5),
    comment: Optional[str] = Form(None, max_length=1000),
    replace_media: bool = Form(False),
    media_files: List[UploadFile] = File(default=[]),
    current_user: User = Depends(get_current_user),
):
    review = await ReviewService.update_review(
        review_id=review_id,
        client_id=str(current_user.id),
        rating=rating,
        comment=comment,
        media_files=media_files if media_files else None,
        replace_media=replace_media,
    )

    return APIResponse(
        message="Review updated successfully",
        data=ReviewResponse.model_validate(review, from_attributes=True),
    )


# ─────────────────────────────────────────────
# DELETE REVIEW (CLIENT)
# ─────────────────────────────────────────────
@router.delete(
    "/{review_id}",
    response_model=MessageResponse,
    summary="Delete own review",
)
async def delete_review(
    review_id: str,
    current_user: User = Depends(get_current_user),
):
    await ReviewService.delete_review(
        review_id=review_id,
        client_id=str(current_user.id),
    )

    return MessageResponse(
        message="Review deleted successfully"
    )


# ─────────────────────────────────────────────
# DELETE REVIEW (ADMIN)
# ─────────────────────────────────────────────
@router.delete(
    "/admin/{review_id}",
    response_model=MessageResponse,
    summary="[ADMIN] Delete any review",
)
async def admin_delete_review(
    review_id: str,
    current_admin: User = Depends(admin_required),
):
    await ReviewService.admin_delete_review(
        review_id=review_id,
        admin_id=str(current_admin.id),
    )

    return MessageResponse(
        message="Review deleted by admin"
    )