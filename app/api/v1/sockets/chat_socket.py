from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from app.core.socket_manager import manager
from app.services.chat_service import ChatService
from app.services.redis_chat_service import RedisChatService
from app.dependencies.websocket_auth import get_current_user_ws
from app.core.exceptions import AppException
from app.models.chat_room import ChatRoom
from app.models.user import UserRole
import logging
import traceback
from datetime import datetime

router = APIRouter(tags=["WebSockets"])
logger = logging.getLogger(__name__)


@router.websocket("/ws/chat/{booking_id}")
async def websocket_chat(websocket: WebSocket, booking_id: str):
    logger.info(f"🔍 Using manager instance ID: {id(manager)}")
    logger.info("=" * 50)
    logger.info(f"CHAT WEBSOCKET CONNECTION ATTEMPT")
    logger.info(f"Booking ID: {booking_id}")
    logger.info(f"Query params: {dict(websocket.query_params)}")
    logger.info("=" * 50)

    # ── Step 1 — Authenticate user from query param token ────────
    try:
        if "token" not in websocket.query_params:
            logger.error("No token found in query parameters")
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="No token provided",
            )
            return

        token = websocket.query_params.get("token")
        logger.info(f"Token found (first 20 chars): {token[:20]}...")

        user = await get_current_user_ws(websocket)

        if not user:
            logger.error("Authentication failed - user is None")
            return

        user_id = str(user.id)
        logger.info(f"✅ Authentication successful for user: {user_id}")
        logger.info(f"User type: {user.user_type}")

    except Exception as e:
        logger.error(f"❌ Authentication failed: {str(e)}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # ── Step 2 — Subscription gate (added) ───────────────────────
    # Admin bypasses. Client needs can_use_messaging (paid plan).
    # Provider needs can_use_messaging (Tier 2+).
    # Check before accepting connection — cheaper than accepting then closing.
    if user.user_type != UserRole.ADMIN:
        try:
            from app.services.subscription_service import SubscriptionService

            features = await SubscriptionService.get_user_features(
                user_id, user.user_type
            )

            if not features.can_use_messaging:
                logger.warning(
                    f"❌ User {user_id} ({user.user_type}) blocked — "
                    f"can_use_messaging=False"
                )
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Your current plan does not include messaging. Please upgrade.",
                )
                return

            logger.info(f"✅ Subscription check passed for user {user_id}")

        except Exception as e:
            logger.error(f"❌ Subscription check failed: {str(e)}")
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return
    # ─────────────────────────────────────────────────────────────

    # ── Step 3 — Accept WebSocket connection ─────────────────────
    await websocket.accept()
    logger.info(f"✅ WebSocket connection accepted for user {user_id}")

    # ── Step 4 — Find chat room ───────────────────────────────────
    try:
        logger.info(f"Looking for chat room with booking_id: {booking_id}")

        room = await ChatRoom.find_one(
            {"booking_id": booking_id, "is_deleted": False}
        )

        if not room:
            logger.error(f"❌ Chat room not found for booking {booking_id}")
            await websocket.send_json({
                "type": "error",
                "error": "Chat not available. Please ensure the booking is confirmed.",
            })
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        logger.info(f"✅ Chat room found: {room.id}")
        logger.info(f"Room client_id: {room.client_id}")
        logger.info(f"Room provider_id: {room.provider_id}")

    except Exception as e:
        logger.error(f"❌ Error finding chat room: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "error": "Failed to access chat room",
        })
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    # ── Step 5 — Check room membership ───────────────────────────
    client_id_str = str(room.client_id)
    provider_id_str = str(room.provider_id)

    logger.info(f"Checking membership - User ID: {user_id}")
    logger.info(f"Client ID: {client_id_str}")
    logger.info(f"Provider ID: {provider_id_str}")

    if user_id not in [client_id_str, provider_id_str]:
        logger.error(f"❌ User {user_id} not authorized for booking {booking_id}")
        await websocket.send_json({
            "type": "error",
            "error": "You are not a participant in this chat",
        })
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    logger.info(f"✅ User authorized for chat room")

    # ── Step 6 — Register connection with socket manager ─────────
    await manager.connect(booking_id, websocket, user_id)
    logger.info(f"✅ User {user_id} connected to booking {booking_id}")

    # ── Step 7 — Track user in Redis ─────────────────────────────
    await RedisChatService.track_user_in_room(str(room.id), user_id)

    # ── Step 8 — Get unread count from Redis ─────────────────────
    unread_count = await RedisChatService.get_unread_count(str(room.id), user_id)

    # ── Step 9 — Send recent messages (last 20) ──────────────────
    try:
        recent_messages = await RedisChatService.get_recent_messages(str(room.id), 20)
        if recent_messages:
            await websocket.send_json({
                "type": "recent_messages",
                "messages": recent_messages,
            })
    except Exception as e:
        logger.error(f"Error sending recent messages: {str(e)}")

    # ── Step 10 — Send connection established ────────────────────
    await websocket.send_json({
        "type": "connection_established",
        "message": "Connected to chat room",
        "booking_id": booking_id,
        "room_id": str(room.id),
        "user_id": user_id,
        "unread_count": unread_count,
        "participants": {
            "client_id": client_id_str,
            "provider_id": provider_id_str,
        },
        "timestamp": datetime.now().isoformat(),
    })

    # ── Main message loop ─────────────────────────────────────────
    try:
        while True:
            try:
                data = await websocket.receive_json()
                logger.info(f"📨 Received message from user {user_id}: {data}")
            except ValueError:
                logger.error("Invalid JSON format")
                await websocket.send_json({
                    "type": "error",
                    "error": "Invalid JSON format",
                })
                continue

            text = data.get("text")
            attachment_url = data.get("attachment_url")
            attachment_type = data.get("attachment_type")

            if not text and not attachment_url:
                await websocket.send_json({
                    "type": "error",
                    "error": "Message must contain text or an attachment",
                })
                continue

            try:
                message = await ChatService.send_message(
                    booking_id=booking_id,
                    sender_id=user_id,
                    background_tasks=None,
                    text=text,
                    attachment_url=attachment_url,
                    attachment_type=attachment_type,
                )
                logger.info(f"✅ Message saved with id: {message.id}")
            except AppException as e:
                logger.error(f"AppException: {e.message}")
                await websocket.send_json({
                    "type": "error",
                    "error": e.message,
                })
                continue
            except Exception as e:
                logger.error(f"Unexpected error saving message: {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "error": "Failed to send message",
                })
                continue

            # Get updated unread count for recipient
            recipient_id = (
                room.provider_id
                if user_id == str(room.client_id)
                else room.client_id
            )
            unread_count_for_recipient = await RedisChatService.get_unread_count(
                str(room.id), recipient_id
            )

            # Broadcast to all room participants except sender
            payload = {
                "type": "new_message",
                "id": str(message.id),
                "sender_id": message.sender_id,
                "sender_type": (
                    "client" if message.sender_id == str(room.client_id) else "provider"
                ),
                "text": message.text,
                "attachment_url": message.attachment_url,
                "attachment_type": message.attachment_type,
                "is_read": message.is_read,
                "created_at": message.created_at.isoformat(),
                "unread_count": unread_count_for_recipient,
            }
            await manager.broadcast(booking_id, payload)
            logger.info(f"📤 Message broadcasted to booking {booking_id}")

            # Confirm delivery to sender only
            await websocket.send_json({
                "type": "message_sent",
                "id": str(message.id),
                "status": "delivered",
                "timestamp": message.created_at.isoformat(),
            })

    except WebSocketDisconnect:
        logger.info(f"👋 Client disconnected: user {user_id}, booking {booking_id}")
    except Exception as e:
        logger.error(f"❌ Unexpected error in WebSocket loop: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        await RedisChatService.remove_user_from_room(str(room.id), user_id)
        await RedisChatService.sync_room_to_mongodb(str(room.id), ChatService)
        await manager.disconnect(booking_id, websocket)
        logger.info(f"Connection cleaned up for user {user_id}, booking {booking_id}")
