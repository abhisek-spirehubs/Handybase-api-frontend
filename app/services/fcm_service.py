import asyncio
import logging
from typing import Optional, Dict, Any

from firebase_admin import messaging

logger = logging.getLogger(__name__)

class FCMService:
    """Low‑level Firebase Cloud Messaging operations."""
    
    @staticmethod
    async def send_to_token(
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        platform_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send a notification to a single device token with retry logic.
        Returns a dict with success flag and either message_id or error.
        """
        # Build the base message
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            token=token,
        )

        # Default platform configs
        android_config = messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                sound="default",
                click_action="FLUTTER_NOTIFICATION_CLICK",
            ),
        )
        apns_config = messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(sound="default", badge=1)
            )
        )

        # Apply overrides if provided
        if platform_overrides:
            if "android" in platform_overrides:
                android_dict = platform_overrides["android"]
                # Override AndroidConfig fields
                if "priority" in android_dict:
                    android_config.priority = android_dict["priority"]
                if "notification" in android_dict:
                    notif_dict = android_dict["notification"]
                    # Build AndroidNotification from dict
                    notif = messaging.AndroidNotification(
                        sound=notif_dict.get("sound", "default"),
                        click_action=notif_dict.get("click_action", "FLUTTER_NOTIFICATION_CLICK"),
                    )
                    android_config.notification = notif
            if "apns" in platform_overrides:
                apns_dict = platform_overrides["apns"]
                # Override APNS fields
                if "payload" in apns_dict:
                    payload_dict = apns_dict["payload"]
                    if "aps" in payload_dict:
                        aps_dict = payload_dict["aps"]
                        aps = messaging.Aps(
                            sound=aps_dict.get("sound", "default"),
                            badge=aps_dict.get("badge", 1),
                        )
                        apns_config.payload.aps = aps

        message.android = android_config
        message.apns = apns_config

        # Retry logic with exponential backoff
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(messaging.send, message)
                logger.info("Push sent to token %s: %s", token[:20], response)
                return {"success": True, "message_id": response}
            except messaging.UnregisteredError:
                logger.warning("Token unregistered %s", token[:20])
                return {"success": False, "error": "Unregistered", "should_remove": True}
            except messaging.NotFoundError:
                logger.warning("Token not found %s", token[:20])
                return {"success": False, "error": "Not found", "should_remove": True}
            except messaging.QuotaExceededError:
                logger.warning("Quota exceeded, attempt %d/%d", attempt+1, max_retries)
                await asyncio.sleep(2 ** attempt)
                continue
            except messaging.ApiCallError as e:
                # Check error code for invalid token
                if e.code == messaging.ErrorCode.INVALID_ARGUMENT:
                    logger.warning("Invalid token %s", token[:20])
                    return {"success": False, "error": "Invalid token", "should_remove": True}
                # Otherwise, unexpected API error
                logger.exception("Unexpected API error")
                return {"success": False, "error": str(e)}
            except Exception as e:
                logger.exception("Unexpected error sending push")
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "Max retries exceeded"}