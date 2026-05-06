# app/services/notification_service.py
from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId

from app.models.notification import Notification
from app.schemas.notification import NotificationCreate, NotificationResponse
from app.utils.logger import app_logger
from app.core.exceptions import (
    NotFoundException,
    ForbiddenException,
    AppException,
    ValidationException,
)


class NotificationService:

    # ─────────────────────────────────────────
    # Create in‑app notification only
    # ─────────────────────────────────────────

    @staticmethod
    async def create_notification(data: NotificationCreate) -> Optional[Notification]:
        """Create an in‑app notification. No push involved."""
        try:
            notif = Notification(
                user_id=data.user_id,
                title=data.title,
                note=data.note,
                type=data.type,
                path=data.path,
                is_admin=data.is_admin,
                created_by=data.user_id,
            )
            await notif.insert()
            return notif
        except Exception:
            app_logger.exception(
                "Failed to create notification for user_id=%s", data.user_id
            )
            return None

    @staticmethod
    async def notify(
        user_id: str,
        title: str,
        body: str,
        notification_type: str,
        data: Optional[dict] = None,
        path: Optional[str] = None,
        is_admin: bool = False,
    ) -> None:
        """Convenience method to create an in‑app notification."""
        await NotificationService.create_notification(
            NotificationCreate(
                user_id=user_id,
                title=title,
                note=body,
                type=notification_type,
                path=path,
                is_admin=is_admin,
                data=data,
            )
        )

    # ─────────────────────────────────────────
    # Read
    # ─────────────────────────────────────────

    @staticmethod
    async def get_notifications(
        user_id: str,
        page: int,
        limit: int,
        is_read: bool | None = None,
    ) -> dict:
        try:
            skip = (page - 1) * limit
            query: dict = {"user_id": user_id, "is_deleted": False}

            if is_read is not None:
                query["is_read"] = is_read

            # 1. Count total matching documents (fast, index‑only)
            total = await Notification.find(query).count()

            # 2. Fetch only the required page (sort, skip, limit)
            notifications = await Notification.find(query) \
                .sort("-created_at") \
                .skip(skip) \
                .limit(limit) \
                .to_list()

            data = [
                NotificationResponse.model_validate(notif, from_attributes=True)
                for notif in notifications
            ]

            pages = max(1, (total + limit - 1) // limit)

            return {
                "Success": True,
                "message": "notificatons fetched successfully",
                "total": total,
                "data": data,
            }

        except Exception:
            app_logger.exception(
                "Failed to fetch notifications for user_id=%s", user_id
            )
            raise AppException("Failed to fetch notifications", status_code=500)

    @staticmethod
    async def get_unread_count(user_id: str) -> dict:
        try:
            count = await Notification.find({
                "user_id": user_id,
                "is_read": False,
                "is_deleted": False,
            }).count()
            return {"count": count}
        except Exception:
            app_logger.exception(
                "Failed to fetch unread count for user_id=%s", user_id
            )
            raise AppException("Failed to fetch unread count", status_code=500)

    # ─────────────────────────────────────────
    # Update
    # ─────────────────────────────────────────

    @staticmethod
    async def mark_all_as_read(user_id: str) -> dict:
        try:
            now = datetime.now(timezone.utc)
            await Notification.find({
                "user_id": user_id,
                "is_read": False,
                "is_deleted": False,
            }).update({"$set": {
                "is_read": True,
                "updated_at": now,
                "updated_by": user_id,
            }})
            return {"success": True, "message": "All notifications marked as read"}
        except Exception:
            app_logger.exception(
                "Failed to mark all read for user_id=%s", user_id
            )
            raise AppException("Failed to mark notifications as read", status_code=500)

    @staticmethod
    async def mark_as_read(notification_id: str, user_id: str) -> dict:
        try:
            if not ObjectId.is_valid(notification_id):
                raise ValidationException("Invalid notification ID")

            notification = await Notification.get(notification_id)
            if not notification or notification.is_deleted:
                raise NotFoundException("Notification not found")
            if notification.user_id != user_id:
                raise ForbiddenException("Not allowed")
            if notification.is_read:
                return {"success": True, "message": "Notification already read"}

            notification.is_read = True
            notification.updated_by = user_id
            await notification.save()

            return {"success": True, "message": "Notification marked as read"}

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to mark notification %s as read", notification_id
            )
            raise AppException("Failed to mark notification as read", status_code=500)

    # ─────────────────────────────────────────
    # Delete
    # ─────────────────────────────────────────

    @staticmethod
    async def delete_notification(notification_id: str, user_id: str) -> dict:
        try:
            if not ObjectId.is_valid(notification_id):
                raise ValidationException("Invalid notification ID")

            notification = await Notification.get(notification_id)
            if not notification or notification.is_deleted:
                raise NotFoundException("Notification not found")
            if notification.user_id != user_id:
                raise ForbiddenException("Not allowed")

            await notification.soft_delete(user_id)
            return {"success": True, "message": "Notification deleted"}

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to delete notification %s", notification_id
            )
            raise AppException("Failed to delete notification", status_code=500)

    @staticmethod
    async def clear_notifications(user_id: str) -> dict:
        try:
            now = datetime.now(timezone.utc)
            await Notification.find({
                "user_id": user_id,
                "is_deleted": False,
            }).update({"$set": {
                "is_deleted": True,
                "deleted_at": now,
                "deleted_by": user_id,
                "updated_at": now,
                "updated_by": user_id,
            }})
            return {"success": True, "message": "All notifications cleared"}
        except Exception:
            app_logger.exception(
                "Failed to clear notifications for user_id=%s", user_id
            )
            raise AppException("Failed to clear notifications", status_code=500)