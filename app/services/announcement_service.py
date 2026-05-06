from __future__ import annotations

from bson import ObjectId
from fastapi import BackgroundTasks

from app.models.announcement import Announcement
from app.models.user import User
from app.schemas.announcement import AnnouncementCreate, AnnouncementUpdate
from app.services.notification_service import NotificationService
from app.schemas.notification import NotificationCreate
from app.utils.logger import app_logger
from app.core.exceptions import AppException, NotFoundException, ValidationException


class AnnouncementService:

    # ── Create + broadcast ────────────────────────────────────────────────────

    @staticmethod
    async def create_announcement(
        data:             AnnouncementCreate,
        admin_id:         str,
        background_tasks: BackgroundTasks,
    ) -> Announcement:
        try:
            ann = Announcement(
                title=data.title,
                message=data.message,
                created_by=admin_id,
            )
            await ann.insert()

            # Notify all active non-deleted users in background
            background_tasks.add_task(
                AnnouncementService._broadcast_notification,
                announcement_id=str(ann.id),
                title=data.title,
                message=data.message,
            )

            app_logger.info("Announcement created id=%s admin=%s", str(ann.id), admin_id)
            return ann

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to create announcement")
            raise AppException("Failed to create announcement", status_code=500)

    @staticmethod
    async def _broadcast_notification(
        announcement_id: str,
        title:           str,
        message:         str,
    ) -> None:
        """
        Sends push notification to every active user.
        Runs in background — failures are logged, never raised.
        """
        try:
            users = await User.find(
                User.is_deleted == False,
            ).to_list()

            app_logger.info(
                "[announcement] Broadcasting to %d users announcement_id=%s",
                len(users), announcement_id,
            )

            for user in users:
                try:
                    await NotificationService.create_notification(
                        NotificationCreate(
                            user_id=str(user.id),
                            title=title,
                            note=message,
                            type="ANNOUNCEMENT",
                            fcm_token=user.fcm_token,
                            data={
                                "announcement_id": announcement_id,
                                "type":            "ANNOUNCEMENT",
                            },
                        )
                    )
                except Exception as e:
                    app_logger.error(
                        "[announcement] Notify failed user_id=%s: %s", str(user.id), e
                    )

        except Exception:
            app_logger.exception(
                "[announcement] Broadcast failed announcement_id=%s", announcement_id
            )

    # ── List — paginated ──────────────────────────────────────────────────────

    @staticmethod
    async def get_all(page: int, limit: int, include_inactive: bool = False) -> dict:
        try:
            skip = (page - 1) * limit
            query = [Announcement.is_deleted == False]
            if not include_inactive:
                query.append(Announcement.is_active == True)

            total = await Announcement.find(*query).count()
            items = await Announcement.find(*query) \
                .sort("-created_at") \
                .skip(skip) \
                .limit(limit) \
                .to_list()

            return {
                "message": "Announcements fetched successfully",
                "total": total,
                "data": items,
            }
        except Exception:
            app_logger.exception("Failed to fetch announcements")
            raise AppException("Failed to fetch announcements", status_code=500)

    # ── Get single ────────────────────────────────────────────────────────────

    @staticmethod
    async def get_by_id(announcement_id: str) -> Announcement:
        try:
            if not ObjectId.is_valid(announcement_id):
                raise ValidationException("Invalid announcement id")

            ann = await Announcement.get(announcement_id)
            if not ann or ann.is_deleted:
                raise NotFoundException("Announcement not found")

            return ann

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to fetch announcement id=%s", announcement_id)
            raise AppException("Failed to fetch announcement", status_code=500)

    # ── Update ────────────────────────────────────────────────────────────────

    @staticmethod
    async def update(
        announcement_id: str,
        admin_id:        str,
        data:            AnnouncementUpdate,
    ) -> Announcement:
        try:
            if not ObjectId.is_valid(announcement_id):
                raise ValidationException("Invalid announcement id")

            ann = await Announcement.get(announcement_id)
            if not ann or ann.is_deleted:
                raise NotFoundException("Announcement not found")

            for key, value in data.model_dump(exclude_unset=True).items():
                setattr(ann, key, value)

            ann.updated_by = admin_id
            await ann.save()

            app_logger.info("Announcement updated id=%s admin=%s", announcement_id, admin_id)
            return ann

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to update announcement id=%s", announcement_id)
            raise AppException("Failed to update announcement", status_code=500)

    # ── Delete ────────────────────────────────────────────────────────────────

    @staticmethod
    async def delete(announcement_id: str, admin_id: str) -> None:
        try:
            if not ObjectId.is_valid(announcement_id):
                raise ValidationException("Invalid announcement id")

            ann = await Announcement.get(announcement_id)
            if not ann or ann.is_deleted:
                raise NotFoundException("Announcement not found")

            await ann.soft_delete(admin_id)

            app_logger.info("Announcement deleted id=%s admin=%s", announcement_id, admin_id)

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to delete announcement id=%s", announcement_id)
            raise AppException("Failed to delete announcement", status_code=500)