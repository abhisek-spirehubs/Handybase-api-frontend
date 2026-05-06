from datetime import datetime, timezone
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from typing import List, Optional

from fastapi import UploadFile

from app.models.review import Review
from app.models.user import User, UserRole
from app.models.booking import Booking, BookingStatus
from app.schemas.common import StatusEnum
from app.utils.file_upload import save_file
from app.utils.logger import app_logger
from app.core.exceptions import (
    NotFoundException,
    ForbiddenException,
    ValidationException,
    AppException,
)

MAX_REVIEW_MEDIA   = 5
ALLOWED_IMAGE_EXTS = {"jpg", "jpeg", "png", "webp", "gif"}
ALLOWED_VIDEO_EXTS = {"mp4", "mov", "avi", "mkv", "webm"}
ALLOWED_MEDIA_EXTS = ALLOWED_IMAGE_EXTS | ALLOWED_VIDEO_EXTS


async def _save_review_media(files: List[UploadFile]) -> List[str]:
    if len(files) > MAX_REVIEW_MEDIA:
        raise ValidationException(
            f"You can upload a maximum of {MAX_REVIEW_MEDIA} media files per review."
        )

    urls = []
    for file in files:
        ext = (file.filename or "").rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED_MEDIA_EXTS:
            raise ValidationException(
                f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_MEDIA_EXTS))}"
            )
        url = await save_file(file, "reviews/media")
        urls.append(url)

    return urls


class ReviewService:

    # ─────────────────────────────────────────
    # CREATE
    # ─────────────────────────────────────────
    @staticmethod
    async def create_review(
        client_id: str,
        client_type: UserRole,
        booking_id: str,
        rating: float,
        comment: Optional[str] = None,
        media_files: List[UploadFile] = None,
    ) -> Review:

        if client_type != UserRole.CLIENT:
            raise ForbiddenException("Only clients can create reviews")

        if not ObjectId.is_valid(booking_id):
            raise ValidationException("Invalid booking id")

        booking = await Booking.get(booking_id)
        if not booking or booking.is_deleted:
            raise NotFoundException("Booking not found")

        if booking.client_id != client_id:
            raise ForbiddenException("Not allowed to review this booking")

        if booking.booking_status != BookingStatus.COMPLETED:
            raise AppException(
                "You can only review a completed booking",
                status_code=400,
            )

        existing = await Review.find_one({
            "booking_id": booking_id,
            "is_deleted": False,
        })
        if existing:
            raise AppException("You have already reviewed this booking", status_code=409)

        media_urls: List[str] = []
        if media_files:
            media_urls = await _save_review_media(media_files)

        review = Review(
            client_id=client_id,
            provider_id=booking.provider_id,
            service_id=booking.service_id,
            booking_id=booking_id,
            rating=rating,
            comment=comment,
            media_urls=media_urls,
            created_by=client_id,
            status=StatusEnum.ACTIVE,
        )

        try:
            await review.insert()
        except DuplicateKeyError:
            raise AppException("You have already reviewed this booking", status_code=409)

        await ReviewService._update_provider_rating(booking.provider_id)
        return review


    # ─────────────────────────────────────────
    # UPDATE
    # ─────────────────────────────────────────
    @staticmethod
    async def update_review(
        review_id: str,
        client_id: str,
        rating: Optional[float] = None,
        comment: Optional[str] = None,
        media_files: List[UploadFile] = None,
        replace_media: bool = False,
    ) -> Review:

        if not ObjectId.is_valid(review_id):
            raise ValidationException("Invalid review id")

        review = await Review.get(review_id)
        if not review or review.is_deleted:
            raise NotFoundException("Review not found")

        if review.client_id != client_id:
            raise ForbiddenException("You can only update your own reviews")

        if rating is None and comment is None and not media_files:
            raise ValidationException(
                "At least one field must be provided"
            )

        rating_changed = False

        if rating is not None and rating != review.rating:
            review.rating = rating
            rating_changed = True

        if comment is not None:
            review.comment = comment

        if media_files:
            new_urls = await _save_review_media(media_files)
            if replace_media:
                review.media_urls = new_urls
            else:
                combined = review.media_urls + new_urls
                if len(combined) > MAX_REVIEW_MEDIA:
                    raise ValidationException(
                        f"Total media cannot exceed {MAX_REVIEW_MEDIA}"
                    )
                review.media_urls = combined

        review.updated_by = client_id
        await review.save()

        if rating_changed:
            await ReviewService._update_provider_rating(review.provider_id)

        return review


    # ─────────────────────────────────────────
    # DELETE (CLIENT)
    # ─────────────────────────────────────────
    @staticmethod
    async def delete_review(review_id: str, client_id: str) -> None:

        if not ObjectId.is_valid(review_id):
            raise ValidationException("Invalid review id")

        review = await Review.get(review_id)
        if not review or review.is_deleted:
            raise NotFoundException("Review not found")

        if review.client_id != client_id:
            raise ForbiddenException("Not allowed")

        provider_id = review.provider_id
        await review.soft_delete(client_id)

        await ReviewService._update_provider_rating(provider_id)


    # ─────────────────────────────────────────
    # DELETE (ADMIN)
    # ─────────────────────────────────────────
    @staticmethod
    async def admin_delete_review(review_id: str, admin_id: str) -> None:

        if not ObjectId.is_valid(review_id):
            raise ValidationException("Invalid review id")

        review = await Review.get(review_id)
        if not review or review.is_deleted:
            raise NotFoundException("Review not found")

        provider_id = review.provider_id
        await review.soft_delete(admin_id)

        await ReviewService._update_provider_rating(provider_id)


    # ─────────────────────────────────────────
    # LIST (PROVIDER)
    # ─────────────────────────────────────────
    @staticmethod
    async def get_provider_reviews(
        provider_id: str,
        page: int,
        limit: int,
        min_rating: Optional[float] = None,
    ) -> dict:

        if not ObjectId.is_valid(provider_id):
            raise ValidationException("Invalid provider id")

        skip = (page - 1) * limit

        query = {"provider_id": provider_id, "is_deleted": False}
        if min_rating is not None:
            query["rating"] = {"$gte": min_rating}

        total = await Review.find(query).count()

        reviews = (
            await Review.find(query)
            .sort("-created_at")
            .skip(skip)
            .limit(limit)
            .to_list()
        )

        data = []
        for rev in reviews:
            d = rev.model_dump()
            d["id"] = str(rev.id)
            data.append(d)

        return {
            "total": total,
            "data": data,
        }


    # ─────────────────────────────────────────
    # LIST (ADMIN)
    # ─────────────────────────────────────────
    @staticmethod
    async def get_all_reviews(
        page: int,
        limit: int,
        provider_id: Optional[str] = None,
        client_id: Optional[str] = None,
        min_rating: Optional[float] = None,
        include_deleted: bool = False,
    ) -> dict:

        skip = (page - 1) * limit
        query = {}

        if not include_deleted:
            query["is_deleted"] = False

        if provider_id:
            if not ObjectId.is_valid(provider_id):
                raise ValidationException("Invalid provider id")
            query["provider_id"] = provider_id

        if client_id:
            if not ObjectId.is_valid(client_id):
                raise ValidationException("Invalid client id")
            query["client_id"] = client_id

        if min_rating is not None:
            query["rating"] = {"$gte": min_rating}

        total = await Review.find(query).count()

        reviews = (
            await Review.find(query)
            .sort("-created_at")
            .skip(skip)
            .limit(limit)
            .to_list()
        )

        data = []
        for rev in reviews:
            d = rev.model_dump()
            d["id"] = str(rev.id)
            data.append(d)

        return {
            "total": total,
            "data": data,
        }


    # ─────────────────────────────────────────
    # INTERNAL
    # ─────────────────────────────────────────
    @staticmethod
    async def _update_provider_rating(provider_id: str) -> None:
        try:
            pipeline = [
                {"$match": {"provider_id": provider_id, "is_deleted": False}},
                {"$group": {
                    "_id": None,
                    "avg_rating": {"$avg": "$rating"},
                    "total": {"$sum": 1},
                }},
            ]

            collection = Review.get_pymongo_collection()
            result = await collection.aggregate(pipeline).to_list(length=None)

            avg = round(result[0]["avg_rating"], 2) if result else 0.0
            count = result[0]["total"] if result else 0

            user_collection = User.get_pymongo_collection()
            await user_collection.update_one(
                {"_id": ObjectId(provider_id)},
                {"$set": {
                    "rating": avg,
                    "total_reviews": count,
                    "updated_at": datetime.now(timezone.utc),
                }},
            )
        except Exception:
            app_logger.exception(
                "Failed to update provider rating provider_id=%s", provider_id
            )