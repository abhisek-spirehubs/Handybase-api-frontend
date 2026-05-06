from __future__ import annotations

from typing import List

from app.models.booking import Booking, BookingStatus
from app.models.client_review import ClientReview
from app.models.user import User, UserRole
from app.schemas.client_rating import ClientReviewCreate
from app.core.exceptions import (
    ValidationException, NotFoundException,
    ForbiddenException, AppException,
)
from app.utils.logger import app_logger
from bson import ObjectId


async def create_client_review(
    provider: User,
    data: ClientReviewCreate,
) -> ClientReview:
    """
    Provider submits a rating for a client after job completion.

    Rules:
    - Booking must belong to this provider
    - Booking must be COMPLETED
    - One review per booking (enforced by unique index + explicit check)
    """
    try:
        # ── Validate booking_id ───────────────────────────────────────────
        if not ObjectId.is_valid(data.booking_id):
            raise ValidationException("Invalid booking id")

        booking = await Booking.get(data.booking_id)
        if not booking or booking.is_deleted:
            raise NotFoundException("Booking not found")

        if booking.provider_id != str(provider.id):
            raise ForbiddenException(
                "You can only rate clients from your own bookings"
            )

        if booking.booking_status != BookingStatus.COMPLETED:
            raise ForbiddenException(
                "You can only rate a client after the job is completed"
            )

        # ── Check for duplicate ───────────────────────────────────────────
        existing = await ClientReview.find_one(
            ClientReview.booking_id == data.booking_id,
            ClientReview.is_deleted == False,
        )
        if existing:
            raise ValidationException(
                "You have already rated the client for this booking"
            )

        # ── Create review ─────────────────────────────────────────────────
        review = ClientReview(
            provider_id=str(provider.id),
            client_id=booking.client_id,
            booking_id=data.booking_id,
            service_id=booking.service_id,
            rating=data.rating,
            payment_behavior=data.payment_behavior,
            communication=data.communication,
            comment=data.comment,
            created_by=str(provider.id),
        )
        await review.insert()
    
        return review

    except AppException:
        raise
    except Exception:
        app_logger.exception(
            "Failed to create client review provider_id=%s booking_id=%s",
            str(provider.id), data.booking_id,
        )
        raise AppException("Failed to submit client review", status_code=500)


async def get_reviews_by_provider(
    provider_id: str,
    page: int = 1,
    limit: int = 10,
) -> dict:
    """
    All client reviews a provider has submitted — paginated.
    """
    try:
        skip  = (page - 1) * limit
        query = [
            ClientReview.provider_id == provider_id,
            ClientReview.is_deleted == False,
        ]
        total   = await ClientReview.find(*query).count()
        reviews = (
            await ClientReview.find(*query)
            .sort("-created_at")
            .skip(skip)
            .limit(limit)
            .to_list()
        )
        return {
            "total":   total,
            "page":    page,
            "limit":   limit,
            "pages":   max(1, (total + limit - 1) // limit),
            "reviews": reviews,
        }
    except AppException:
        raise
    except Exception:
        app_logger.exception(
            "Failed to get reviews by provider provider_id=%s", provider_id
        )
        raise AppException("Failed to fetch reviews", status_code=500)


async def get_reviews_for_client(
    client_id: str,
    page: int = 1,
    limit: int = 10,
) -> dict:
    """
    All ratings a client has received from providers.
    Admin-only endpoint — not exposed publicly.
    """
    try:
        skip  = (page - 1) * limit
        query = [
            ClientReview.client_id == client_id,
            ClientReview.is_deleted == False,
        ]
        total   = await ClientReview.find(*query).count()
        reviews = (
            await ClientReview.find(*query)
            .sort("-created_at")
            .skip(skip)
            .limit(limit)
            .to_list()
        )
        return {
            "total":   total,
            "page":    page,
            "limit":   limit,
            "pages":   max(1, (total + limit - 1) // limit),
            "reviews": reviews,
        }
    except AppException:
        raise
    except Exception:
        app_logger.exception(
            "Failed to get reviews for client client_id=%s", client_id
        )
        raise AppException("Failed to fetch client reviews", status_code=500)


async def delete_client_review(
    user: User,
    review_id: str,
) -> None:
    """
    Soft-delete a client review.

    Access:
    - PROVIDER → only own reviews
    - ADMIN    → any review
    """
    try:
        if not ObjectId.is_valid(review_id):
            raise ValidationException("Invalid review id")

        review = await ClientReview.get(review_id)
        if not review or review.is_deleted:
            raise NotFoundException("Review not found")

        # ── PROVIDER → own only ─────────────────────────
        if user.user_type == UserRole.PROVIDER:
            if review.provider_id != str(user.id):
                raise ForbiddenException("You can only delete your own reviews")

        # ── ADMIN → full access ─────────────────────────
        elif user.user_type == UserRole.ADMIN:
            pass

        # ── OTHERS → deny ───────────────────────────────
        else:
            raise ForbiddenException("Not allowed to delete review")

        await review.soft_delete(str(user.id))

    except AppException:
        raise
    except Exception:
        app_logger.exception(
            "Failed to delete client review review_id=%s", review_id
        )
        raise AppException("Failed to delete review", status_code=500)


async def update_client_review(
    user: User,
    review_id: str,
    rating: float,
    comment: str = None,
) -> ClientReview:
    """
    Update an existing client review.
    Only the original provider can update it.
    """
    try:
        if not ObjectId.is_valid(review_id):
            raise ValidationException("Invalid review id")

        review = await ClientReview.get(review_id)
        if not review or review.is_deleted:
            raise NotFoundException("Review not found")

        if review.provider_id != str(user.id):
            raise ForbiddenException("You can only update your own reviews")

        review.rating = rating
        if comment is not None:
            review.comment = comment

        review.updated_by = str(user.id)
        await review.save()

        return review

    except AppException:
        raise
    except Exception:
        app_logger.exception(
            "Failed to update client review review_id=%s", review_id
        )
        raise AppException("Failed to update review", status_code=500)