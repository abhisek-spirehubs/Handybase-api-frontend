import json
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from app.core.redis_client import get_redis
from app.utils.logger import app_logger
from fastapi import BackgroundTasks


class RedisChatService:
    """
    Service for real-time chat operations using Redis
    Unread counts and recent messages are stored in Redis for fast access
    """
    
    # Redis key patterns
    UNREAD_KEY = "chat:unread:{room_id}:{user_id}"
    ROOM_UNREAD_KEY = "chat:room:{room_id}:unread"
    RECENT_MESSAGES_KEY = "chat:recent:{room_id}"
    ROOM_USERS_KEY = "chat:room:{room_id}:users"
    PENDING_SYNC_KEY = "chat:pending_sync:{room_id}"
    
    @classmethod
    async def _get_redis(cls):
        """Get Redis connection"""
        return await get_redis()
    
    @classmethod
    async def update_unread_count(cls, room_id: str, recipient_id: str, increment: int = 1) -> Optional[int]:
        """
        Update unread count for a recipient in real-time
        Returns the new unread count
        """
        try:
            redis = await cls._get_redis()
            
            # Use Redis hash for room unread counts
            room_unread_key = cls.ROOM_UNREAD_KEY.format(room_id=room_id)
            
            # Increment the count for this recipient
            new_count = await redis.hincrby(room_unread_key, recipient_id, increment)
            
            # Set expiry (7 days) - if room is inactive for 7 days, counts expire
            await redis.expire(room_unread_key, 604800)  # 7 days in seconds
            
            # Mark this room for background sync
            pending_key = cls.PENDING_SYNC_KEY.format(room_id=room_id)
            await redis.setex(pending_key, 3600, "1")  # Mark for sync within 1 hour
            
            app_logger.debug(f"Updated unread count for room {room_id}, user {recipient_id}: {new_count}")
            return new_count
            
        except Exception as e:
            app_logger.error(f"Redis error updating unread count: {str(e)}")
            return None
    
    @classmethod
    async def get_unread_count(cls, room_id: str, user_id: str) -> int:
        """Get current unread count for a user in a room"""
        try:
            redis = await cls._get_redis()
            room_unread_key = cls.ROOM_UNREAD_KEY.format(room_id=room_id)
            
            count = await redis.hget(room_unread_key, user_id)
            return int(count) if count else 0
            
        except Exception as e:
            app_logger.error(f"Redis error getting unread count: {str(e)}")
            return 0
    
    @classmethod
    async def reset_unread_count(cls, room_id: str, user_id: str, background_tasks: BackgroundTasks = None):
        """
        Reset unread count to zero when user reads messages
        Optionally trigger background sync
        """
        try:
            redis = await cls._get_redis()
            room_unread_key = cls.ROOM_UNREAD_KEY.format(room_id=room_id)
            
            await redis.hset(room_unread_key, user_id, 0)
            
            # Mark for background sync if background_tasks provided
            if background_tasks:
                from app.services.chat_service import ChatService
                background_tasks.add_task(
                    cls.sync_room_to_mongodb,
                    room_id=room_id,
                    mongodb_service=ChatService
                )
            
            app_logger.debug(f"Reset unread count for room {room_id}, user {user_id}")
            
        except Exception as e:
            app_logger.error(f"Redis error resetting unread count: {str(e)}")
    
    @classmethod
    async def get_all_unread_counts(cls, room_id: str) -> Dict[str, int]:
        """Get all unread counts for a room (both client and provider)"""
        try:
            redis = await cls._get_redis()
            room_unread_key = cls.ROOM_UNREAD_KEY.format(room_id=room_id)
            
            counts = await redis.hgetall(room_unread_key)
            return {user_id: int(count) for user_id, count in counts.items()}
            
        except Exception as e:
            app_logger.error(f"Redis error getting all unread counts: {str(e)}")
            return {}
    
    @classmethod
    async def store_recent_message(cls, room_id: str, message_data: Dict[str, Any], ttl_seconds: int = 86400):
        """
        Store recent message in Redis list (limited to last 50 messages)
        This allows quick catch-up when reconnecting
        """
        try:
            redis = await cls._get_redis()
            recent_key = cls.RECENT_MESSAGES_KEY.format(room_id=room_id)
            
            # Add message to list
            message_json = json.dumps(message_data, default=str)
            await redis.lpush(recent_key, message_json)
            
            # Keep only last 50 messages
            await redis.ltrim(recent_key, 0, 49)
            
            # Set expiry (1 day)
            await redis.expire(recent_key, ttl_seconds)
            
        except Exception as e:
            app_logger.error(f"Redis error storing recent message: {str(e)}")
    
    @classmethod
    async def get_recent_messages(cls, room_id: str, count: int = 50) -> list:
        """Get recent messages for quick catch-up on reconnect"""
        try:
            redis = await cls._get_redis()
            recent_key = cls.RECENT_MESSAGES_KEY.format(room_id=room_id)
            
            messages = await redis.lrange(recent_key, 0, count - 1)
            return [json.loads(msg) for msg in messages]
            
        except Exception as e:
            app_logger.error(f"Redis error getting recent messages: {str(e)}")
            return []
    
    @classmethod
    async def track_user_in_room(cls, room_id: str, user_id: str):
        """Track which users are active in a room"""
        try:
            redis = await cls._get_redis()
            users_key = cls.ROOM_USERS_KEY.format(room_id=room_id)
            
            await redis.sadd(users_key, user_id)
            await redis.expire(users_key, 3600)  # 1 hour expiry
            
        except Exception as e:
            app_logger.error(f"Redis error tracking user: {str(e)}")
    
    @classmethod
    async def remove_user_from_room(cls, room_id: str, user_id: str):
        """Remove user from room tracking"""
        try:
            redis = await cls._get_redis()
            users_key = cls.ROOM_USERS_KEY.format(room_id=room_id)
            
            await redis.srem(users_key, user_id)
            
        except Exception as e:
            app_logger.error(f"Redis error removing user: {str(e)}")
    
    @classmethod
    async def get_active_users_in_room(cls, room_id: str) -> set:
        """Get all active users in a room"""
        try:
            redis = await cls._get_redis()
            users_key = cls.ROOM_USERS_KEY.format(room_id=room_id)
            
            return await redis.smembers(users_key)
            
        except Exception as e:
            app_logger.error(f"Redis error getting active users: {str(e)}")
            return set()
    
    @classmethod
    async def sync_room_to_mongodb(cls, room_id: str, mongodb_service):
        """
        Sync Redis unread counts to MongoDB
        Called via background tasks
        """
        try:
            # Get all unread counts from Redis
            unread_counts = await cls.get_all_unread_counts(room_id)
            
            if not unread_counts:
                return
            
            # Find the MongoDB room document
            from app.models.chat_room import ChatRoom
            room = await ChatRoom.get(room_id)
            
            if not room or room.is_deleted:
                app_logger.warning(f"Room {room_id} not found in MongoDB for sync")
                return
            
            # Update MongoDB with Redis counts
            update_fields = {}
            if room.client_id in unread_counts:
                update_fields["client_unread_count"] = unread_counts[room.client_id]
            if room.provider_id in unread_counts:
                update_fields["provider_unread_count"] = unread_counts[room.provider_id]
            
            if update_fields:
                update_fields["updated_at"] = datetime.now(timezone.utc)
                await room.update({"$set": update_fields})
                app_logger.info(f"Synced Redis unread counts to MongoDB for room {room_id}: {update_fields}")
                
                # Clear pending sync flag
                redis = await cls._get_redis()
                pending_key = cls.PENDING_SYNC_KEY.format(room_id=room_id)
                await redis.delete(pending_key)
                
        except Exception as e:
            app_logger.error(f"Error syncing room {room_id} to MongoDB: {str(e)}")
    
    @classmethod
    async def sync_all_pending_rooms(cls, mongodb_service):
        """
        Sync all rooms that have pending updates
        Called by periodic background task
        """
        try:
            redis = await cls._get_redis()
            # Find all pending sync keys
            pending_keys = await redis.keys(cls.PENDING_SYNC_KEY.replace("{room_id}", "*"))
            
            for key in pending_keys:
                # Extract room_id from key
                room_id = key.split(":")[-1]  # chat:pending_sync:{room_id}
                await cls.sync_room_to_mongodb(room_id, mongodb_service)
                
        except Exception as e:
            app_logger.error(f"Error syncing all pending rooms: {str(e)}")