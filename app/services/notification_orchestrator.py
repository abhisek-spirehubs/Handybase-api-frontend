from fastapi import BackgroundTasks
from typing import Optional

from app.services.notification_service import NotificationService
from app.services.push_service import PushService
from app.utils.logger import app_logger


class NotificationOrchestrator:
    """Orchestrates sending notifications across multiple channels (in‑app, push, etc.)."""

    @staticmethod
    async def notify_user(
        user_id: str,
        title: str,
        body: str,
        notification_type: str,
        background_tasks: BackgroundTasks,
        data: Optional[dict] = None,
        path: Optional[str] = None,
        is_admin: bool = False,
        send_push: bool = True,
        send_in_app: bool = True,
    ) -> None:
        """
        Send a notification through requested channels.
        - In‑app notification (if send_in_app=True)
        - Push notification (if send_push=True) – executed directly in this background task
        """
        try:
            if send_in_app:
                await NotificationService.notify(
                    user_id=user_id,
                    title=title,
                    body=body,
                    notification_type=notification_type,
                    data=data,
                    path=path,
                    is_admin=is_admin,
                )
                app_logger.debug("In‑app notification created for user %s", user_id)

            if send_push:
                # Since this method is already running in a background task,
                # we can await the push directly without scheduling another task.
                await PushService.send_to_user(
                    user_id=user_id,
                    title=title,
                    body=body,
                    data={**(data or {}), "path": path} if path else data,
                    platform_overrides={
                        "android": {"priority": "high", "notification": {"sound": "default"}},
                        "apns": {"payload": {"aps": {"sound": "default", "badge": 1}}}
                    }
                )
                app_logger.debug("Push sent for user %s", user_id)

        except Exception as e:
            app_logger.exception(
                "Failed to orchestrate notification for user %s: %s", user_id, str(e)
            )