# app/services/push_service.py
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.models.fcm_token import FCMToken
from app.services.fcm_service import FCMService

logger = logging.getLogger(__name__)


class PushService:
    """High‑level push notification service using stored tokens."""

    @staticmethod
    async def register_token(
        user_id: str,
        token: str,
        device_id: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> FCMToken:
        """Register or update a device token for a user."""
        filter_criteria = {"user_id": user_id}
        if device_id:
            filter_criteria["device_id"] = device_id
        else:
            filter_criteria["device_id"] = None

        existing = await FCMToken.find_one(filter_criteria)
        if existing:
            existing.token = token
            existing.platform = platform
            existing.is_active = True
            existing.updated_at = datetime.utcnow()
            await existing.save()
            return existing
        else:
            new_token = FCMToken(
                user_id=user_id,
                token=token,
                device_id=device_id,
                platform=platform,
            )
            await new_token.insert()
            return new_token

    @staticmethod
    async def deactivate_token(token: str) -> None:
        """Soft delete a token (e.g., when FCM returns invalid)."""
        await FCMToken.find_one(FCMToken.token == token).update(
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )

    @staticmethod
    async def deactivate_all_tokens(user_id: str) -> None:
        """Deactivate all tokens for a user (e.g., on logout)."""
        await FCMToken.find(FCMToken.user_id == user_id).update(
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )

    @staticmethod
    async def send_to_user(
        user_id: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        platform_overrides: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Send push notification to all active devices of a user.
        Returns a list of results per token.
        """
        tokens = await FCMToken.find(
            FCMToken.user_id == user_id,
            FCMToken.is_active == True
        ).to_list()

        if not tokens:
            logger.info("No active tokens for user %s", user_id)
            return []

        results = []
        for token_doc in tokens:
            result = await FCMService.send_to_token(
                token=token_doc.token,
                title=title,
                body=body,
                data=data,
                platform_overrides=platform_overrides,
            )
            if not result.get("success") and result.get("should_remove"):
                await PushService.deactivate_token(token_doc.token)
            results.append({"token": token_doc.token, **result})
        return results