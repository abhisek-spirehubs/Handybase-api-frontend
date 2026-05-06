# app/services/chat_service.py

from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from fastapi import BackgroundTasks

from app.models.chat_room import ChatRoom
from app.models.chat_message import ChatMessage
from app.models.booking import Booking, BookingStatus
from app.schemas.chat_message import (
    MessageResponse,
    ConversationResponse,
    ConversationListItem,
    MessagesListResponse,
    ConversationsListResponse,
)
from app.core.exceptions import (
    NotFoundException,
    ForbiddenException,
    ValidationException,
    AppException,
)
from app.utils.logger import app_logger
from app.services.redis_chat_service import RedisChatService


class ChatService:

    @staticmethod
    async def get_conversation(
        booking_id: str,
        user_id: str,
    ) -> ConversationResponse:
        """
        Returns the chat room for a booking with unread count from Redis.
        """
        try:
            if not ObjectId.is_valid(booking_id):
                raise ValidationException("Invalid booking id")

            booking = await Booking.get(booking_id)
            if not booking or booking.is_deleted:
                raise NotFoundException("Booking not found")

            if user_id not in [booking.client_id, booking.provider_id]:
                raise ForbiddenException("Not allowed")

            if booking.booking_status != BookingStatus.CONFIRMED:
                raise AppException(
                    "Chat is only available for confirmed bookings",
                    status_code=400,
                )

            room = await ChatRoom.find_one({
                "booking_id": booking_id,
                "is_deleted": False,
            })

            if not room:
                raise NotFoundException("Chat room not found")

            # Get real‑time unread count from Redis
            redis_unread = await RedisChatService.get_unread_count(str(room.id), user_id)

            # Convert Beanie model to dict and add unread count
            room_dict = room.model_dump()
            room_dict["unread_count"] = redis_unread

            # Validate through schema – this maps _id → id
            return ConversationResponse.model_validate(room_dict)

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to get conversation for booking_id=%s", booking_id)
            raise AppException("Failed to get conversation", status_code=500)

    @staticmethod
    async def send_message(
        booking_id: str,
        sender_id: str,
        background_tasks: Optional[BackgroundTasks] = None,
        text: Optional[str] = None,
        attachment_url: Optional[str] = None,
        attachment_type: Optional[str] = None,
    ) -> ChatMessage:
        """
        Send a message - updates Redis in real‑time, persists to MongoDB in background.
        """
        try:
            if not ObjectId.is_valid(booking_id):
                raise ValidationException("Invalid booking id")

            if not text and not attachment_url:
                raise ValidationException("Message must contain text or an attachment")

            room = await ChatRoom.find_one({
                "booking_id": booking_id,
                "is_deleted": False,
            })

            if not room:
                raise NotFoundException(
                    "Chat room not found. Chat is only available for confirmed bookings."
                )

            if sender_id not in [room.client_id, room.provider_id]:
                raise ForbiddenException("Not allowed")

            recipient_id = room.provider_id if sender_id == room.client_id else room.client_id
            room_id = str(room.id)
            now = datetime.now(timezone.utc)

            # 1. Update unread count in Redis (real‑time)
            await RedisChatService.update_unread_count(
                room_id=room_id,
                recipient_id=recipient_id,
                increment=1
            )

            # 2. Create message object (not yet saved)
            message = ChatMessage(
                chat_room_id=room_id,
                sender_id=sender_id,
                text=text,
                attachment_url=attachment_url,
                attachment_type=attachment_type,
                created_by=sender_id,
                created_at=now,
            )

            # 3. Store recent message in Redis (for quick catch‑up)
            message_data = {
                "id": str(message.id),
                "sender_id": sender_id,
                "text": text,
                "attachment_url": attachment_url,
                "attachment_type": attachment_type,
                "created_at": now.isoformat(),
                "is_read": False
            }
            await RedisChatService.store_recent_message(room_id, message_data)

            # 4. Schedule persistence
            if background_tasks:
                background_tasks.add_task(
                    ChatService._persist_message_to_mongodb,
                    message=message,
                    room=room,
                    sender_id=sender_id,
                    text=text,
                    attachment_url=attachment_url,
                    attachment_type=attachment_type,
                    now=now
                )
            else:
                import asyncio
                asyncio.create_task(
                    ChatService._persist_message_to_mongodb(
                        message=message,
                        room=room,
                        sender_id=sender_id,
                        text=text,
                        attachment_url=attachment_url,
                        attachment_type=attachment_type,
                        now=now
                    )
                )

            return message

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to send message for booking_id=%s", booking_id)
            raise AppException("Failed to send message", status_code=500)

    @staticmethod
    async def _persist_message_to_mongodb(
        message: ChatMessage,
        room: ChatRoom,
        sender_id: str,
        text: Optional[str],
        attachment_url: Optional[str],
        attachment_type: Optional[str],
        now: datetime
    ):
        try:
            await message.insert()
            # Update room with last message info and latest unread counts from Redis
            redis_counts = await RedisChatService.get_all_unread_counts(str(room.id))
            update_fields = {
                "last_message_text": text or "📎 Attachment",
                "last_message_at": now,
                "last_message_sender_id": sender_id,
                "updated_at": now,
                "updated_by": sender_id,
            }
            if room.client_id in redis_counts:
                update_fields["client_unread_count"] = redis_counts[room.client_id]
            if room.provider_id in redis_counts:
                update_fields["provider_unread_count"] = redis_counts[room.provider_id]
            await room.update({"$set": update_fields})
        except Exception as e:
            app_logger.error(f"Failed to persist message to MongoDB: {str(e)}")

    @staticmethod
    async def mark_as_read(
        booking_id: str,
        user_id: str,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> dict:
        try:
            if not ObjectId.is_valid(booking_id):
                raise ValidationException("Invalid booking id")

            room = await ChatRoom.find_one({
                "booking_id": booking_id,
                "is_deleted": False,
            })
            if not room:
                raise NotFoundException("Chat room not found")
            if user_id not in [room.client_id, room.provider_id]:
                raise ForbiddenException("Not allowed")

            room_id = str(room.id)

            # Reset unread count in Redis immediately
            await RedisChatService.reset_unread_count(room_id, user_id, background_tasks)

            # Schedule MongoDB update
            if background_tasks:
                background_tasks.add_task(
                    ChatService._persist_mark_as_read_to_mongodb,
                    room_id=room_id,
                    user_id=user_id,
                    room=room
                )
            else:
                import asyncio
                asyncio.create_task(
                    ChatService._persist_mark_as_read_to_mongodb(
                        room_id=room_id,
                        user_id=user_id,
                        room=room
                    )
                )

            return {"success": True, "message": "Messages marked as read"}

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to mark messages read for booking_id=%s", booking_id)
            raise AppException("Failed to mark messages as read", status_code=500)

    @staticmethod
    async def _persist_mark_as_read_to_mongodb(
        room_id: str,
        user_id: str,
        room: ChatRoom
    ):
        try:
            now = datetime.now(timezone.utc)
            # Mark messages as read in MongoDB
            result = await ChatMessage.find({
                "chat_room_id": room_id,
                "sender_id": {"$ne": user_id},
                "is_read": False,
                "is_deleted": False,
            }).update({"$set": {
                "is_read": True,
                "updated_at": now,
                "updated_by": user_id,
            }})
            # Update room document
            is_client = user_id == room.client_id
            update_field = "client_unread_count" if is_client else "provider_unread_count"
            await room.update({"$set": {
                update_field: 0,
                "updated_at": now,
                "updated_by": user_id,
            }})
        except Exception as e:
            app_logger.error(f"Failed to persist mark as read to MongoDB: {str(e)}")

    @staticmethod
    async def get_messages(
        booking_id: str,
        user_id: str,
        page: int = 1,
        limit: int = 50,
    ) -> MessagesListResponse:
        try:
            if not ObjectId.is_valid(booking_id):
                raise ValidationException("Invalid booking id")

            room = await ChatRoom.find_one({
                "booking_id": booking_id,
                "is_deleted": False,
            })
            if not room:
                raise NotFoundException(
                    "Chat room not found. Chat is only available for confirmed bookings."
                )
            if user_id not in [room.client_id, room.provider_id]:
                raise ForbiddenException("Not allowed")

            room_id = str(room.id)
            skip = (page - 1) * limit

            # Single $facet pipeline (index‑friendly)
            pipeline = [
                {"$match": {"chat_room_id": room_id, "is_deleted": False}},
                {"$facet": {
                    "data": [
                        {"$sort": {"created_at": -1}},
                        {"$skip": skip},
                        {"$limit": limit},
                    ],
                    "total": [{"$count": "count"}],
                }},
            ]
            collection = ChatMessage.get_pymongo_collection()
            result = await collection.aggregate(pipeline).to_list(length=1)
            facet = result[0] if result else {"data": [], "total": []}
            total = facet["total"][0]["count"] if facet["total"] else 0

            # Convert raw docs to MessageResponse (alias handles _id → id)
            data = [MessageResponse.model_validate(doc) for doc in facet["data"]]

            unread_count = await RedisChatService.get_unread_count(room_id, user_id)

            return MessagesListResponse(
                success=True,
                message="Messages fetched successfully",
                total=total,
                data=data,
                unread_count=unread_count,
            )

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to fetch messages for booking_id=%s", booking_id)
            raise AppException("Failed to fetch messages", status_code=500)

    @staticmethod
    async def get_all_conversations(
        user_id: str,
        page: int = 1,
        limit: int = 20,
    ) -> ConversationsListResponse:
        try:
            skip = (page - 1) * limit
            pipeline = [
                {
                    "$match": {
                        "$or": [
                            {"client_id": user_id},
                            {"provider_id": user_id}
                        ],
                        "is_deleted": False
                    }
                },
                {
                    "$facet": {
                        "data": [
                            {"$sort": {"last_message_at": -1}},
                            {"$skip": skip},
                            {"$limit": limit},
                        ],
                        "total": [{"$count": "count"}],
                    }
                },
            ]

            collection = ChatRoom.get_pymongo_collection()
            result = await collection.aggregate(pipeline).to_list(length=1)
            facet = result[0] if result else {"data": [], "total": []}
            total = facet["total"][0]["count"] if facet["total"] else 0

            conversations = []
            for room_doc in facet["data"]:
                room_id = str(room_doc["_id"])
                unread_count = await RedisChatService.get_unread_count(room_id, user_id)
                is_client = user_id == room_doc.get("client_id")

                conversations.append(ConversationListItem(
                    room_id=room_id,
                    booking_id=room_doc["booking_id"],
                    client_id=room_doc["client_id"],
                    provider_id=room_doc["provider_id"],
                    other_party_id=room_doc["provider_id"] if is_client else room_doc["client_id"],
                    unread_count=unread_count,
                    last_message={
                        "text": room_doc.get("last_message_text"),
                        "sender_id": room_doc.get("last_message_sender_id"),
                        "timestamp": room_doc.get("last_message_at").isoformat() if room_doc.get("last_message_at") else None
                    } if room_doc.get("last_message_text") else None,
                    created_at=room_doc.get("created_at").isoformat() if room_doc.get("created_at") else None,
                ))

            return ConversationsListResponse(
                success=True,
                message="Conversations fetched successfully",
                total=total,
                data=conversations,
            )

        except Exception:
            app_logger.exception("Failed to fetch conversations for user_id=%s", user_id)
            raise AppException("Failed to fetch conversations", status_code=500)

    @staticmethod
    async def get_total_unread_count(user_id: str) -> dict:
        try:
            rooms = await ChatRoom.find({
                "$or": [
                    {"client_id": user_id},
                    {"provider_id": user_id}
                ],
                "is_deleted": False
            }).to_list()

            total_unread = 0
            conversations_with_unread = 0
            for room in rooms:
                unread = await RedisChatService.get_unread_count(str(room.id), user_id)
                total_unread += unread
                if unread > 0:
                    conversations_with_unread += 1

            return {
                "total_unread_count": total_unread,
                "conversations_with_unread": conversations_with_unread
            }

        except Exception:
            app_logger.exception("Failed to get total unread count for user_id=%s", user_id)
            raise AppException("Failed to get total unread count", status_code=500)