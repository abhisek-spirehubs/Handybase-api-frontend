import asyncio
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket
from app.core.redis_client import get_redis
from app.utils.logger import app_logger

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Map room_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Map WebSocket -> sender_id (to track who sent what)
        self.connection_users: Dict[WebSocket, str] = {}
        self.redis = None
        self.pubsub = None
        self._listen_task = None
        self._is_initialized = False

    async def initialize_redis(self):
        """Initialize Redis connection and start PubSub listener"""
        if self._is_initialized:
            return
            
        try:
            self.redis = await get_redis()
            self.pubsub = self.redis.pubsub()
            
            # ✅ Use psubscribe for pattern matching
            await self.pubsub.psubscribe("chat:*")
            
            self._listen_task = asyncio.create_task(self._redis_listener())
            self._is_initialized = True
            
            app_logger.info("Redis connected and Pub/Sub initialized with pattern 'chat:*'")
        except Exception as e:
            app_logger.error(f"Redis initialization failed: {str(e)}")
            raise

    async def _redis_listener(self):
        """Listen for Redis PubSub messages and broadcast to local connections"""
        try:
            app_logger.info("🎧 Redis listener started, waiting for messages...")
            
            async for message in self.pubsub.listen():
                # ✅ Handle 'pmessage' type for pattern subscriptions
                if message["type"] == "pmessage":
                    channel = message["channel"]
                    data_str = message["data"]
                    
                    # Extract room_id from channel name (e.g., "chat:booking_123" -> "booking_123")
                    room_id = channel.split(":", 1)[1] if ":" in channel else channel
                    
                    try:
                        data = json.loads(data_str)
                        logger.info(f"Redis message received for room '{room_id}': type={data.get('type')}")
                        
                        # ✅ Extract sender_id from message to avoid echo
                        sender_id = data.get("sender_id")
                        
                        # Broadcast to local WebSocket connections (excluding sender)
                        await self._broadcast_local(room_id, data, exclude_sender_id=sender_id)
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to decode Redis message: {e}")
                        
                elif message["type"] == "psubscribe":
                    logger.info(f"Subscribed to pattern: {message['pattern']}")
                    
        except asyncio.CancelledError:
            logger.info("Redis listener task cancelled")
            raise
        except Exception as e:
            logger.error(f"Redis listener error: {str(e)}", exc_info=True)
            # Attempt to restart listener
            await asyncio.sleep(5)
            if self._is_initialized:
                self._listen_task = asyncio.create_task(self._redis_listener())

    async def connect(self, room_id: str, websocket: WebSocket, user_id: str):
        """
        Register a WebSocket connection for a room
        
        Args:
            room_id: The booking/room identifier
            websocket: The WebSocket connection
            user_id: The user ID of the connected user
        """
        # Initialize Redis on first connection
        if not self._is_initialized:
            await self.initialize_redis()
        
        if room_id not in self.active_connections:
            self.active_connections[room_id] = set()
            logger.info(f"[MANAGER] Created new room set for '{room_id}'")
        
        # Store the connection and associate it with user_id
        self.active_connections[room_id].add(websocket)
        self.connection_users[websocket] = user_id
        
        logger.info(
            f"[MANAGER] User '{user_id}' connected to room '{room_id}' | "
            f"Local connections={len(self.active_connections[room_id])} | "
            f"Total rooms={len(self.active_connections)}"
        )

    async def disconnect(self, room_id: str, websocket: WebSocket):
        """Unregister a WebSocket connection from a room"""
        user_id = self.connection_users.get(websocket, "unknown")
        
        if room_id in self.active_connections:
            self.active_connections[room_id].discard(websocket)
            
            remaining = len(self.active_connections[room_id])
            
            if remaining == 0:
                del self.active_connections[room_id]
                app_logger.info(f"[MANAGER] Removed empty room '{room_id}'")
            else:
                app_logger.info(f"[MANAGER] Room '{room_id}' has {remaining} connection(s) remaining")
        
        # Clean up user mapping
        if websocket in self.connection_users:
            del self.connection_users[websocket]
        
        logger.info(f"[MANAGER] User '{user_id}' disconnected from room '{room_id}'")

    async def _broadcast_local(self, room_id: str, message: dict, exclude_sender_id: str = None):
        """
        Send message to local WebSocket connections in a room
        
        Args:
            room_id: The room to broadcast to
            message: The message payload
            exclude_sender_id: Optional sender_id to exclude (prevents echo)
        """
        if room_id not in self.active_connections:
            logger.debug(f"[MANAGER] No local connections for room '{room_id}'")
            return
        
        connections = self.active_connections[room_id].copy()
        disconnected = set()
        
        sent_count = 0
        skipped_count = 0
        
        for conn in connections:
            # Skip sending to the original sender to prevent echo
            conn_user_id = self.connection_users.get(conn)
            if exclude_sender_id and conn_user_id == exclude_sender_id:
                logger.debug(f"[MANAGER] Skipping echo to sender '{exclude_sender_id}'")
                skipped_count += 1
                continue
            
            try:
                await conn.send_json(message)
                sent_count += 1
                logger.debug(f"Message sent to user '{conn_user_id}' in room '{room_id}'")
            except Exception as e:
                logger.error(f"Error sending to user '{conn_user_id}' in room '{room_id}': {str(e)}")
                disconnected.add(conn)
        
        logger.info(
            f"[MANAGER] Broadcast complete for room '{room_id}': "
            f"sent={sent_count}, skipped={skipped_count}, failed={len(disconnected)}"
        )
        
        # Clean up disconnected clients
        for conn in disconnected:
            await self.disconnect(room_id, conn)

    async def broadcast(self, room_id: str, message: dict):
        """
        Broadcast message to all connections across all server instances.
        Publishes to Redis PubSub, which then distributes to all servers.
        
        The Redis listener will handle broadcasting to local connections,
        automatically excluding the original sender.
        """
        logger.info(f"[MANAGER] Broadcasting message to room '{room_id}': type={message.get('type')}")
        
        if self.redis:
            try:
                channel = f"chat:{room_id}"
                message_json = json.dumps(message)
                
                # Publish to Redis - this will be received by ALL server instances
                subscribers = await self.redis.publish(channel, message_json)
                
                logger.info(
                    f"[MANAGER] Published to Redis channel '{channel}' | "
                    f"Active subscribers={subscribers}"
                )
                
                #  NOTE: We rely on the Redis listener to handle local broadcasting
                # This ensures consistent behavior across all servers and prevents duplicate sends
                
            except Exception as e:
                logger.error(f"[MANAGER] Redis publish error: {str(e)}")
                # Fallback to local broadcast only (without excluding sender since it's a fallback)
                await self._broadcast_local(room_id, message)
        else:
            logger.warning("[MANAGER] Redis not available, using local broadcast only")
            await self._broadcast_local(room_id, message)

    async def cleanup(self):
        """Clean up Redis connections and listeners"""
        logger.info("[MANAGER] Starting cleanup...")
        
        # Cancel listener task
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        
        # Unsubscribe and close PubSub
        if self.pubsub:
            try:
                await self.pubsub.punsubscribe("chat:*")
                await self.pubsub.close()
            except Exception as e:
                logger.error(f"Error closing pubsub: {e}")
        
        # Close Redis connection
        if self.redis:
            try:
                await self.redis.close()
            except Exception as e:
                logger.error(f"Error closing redis: {e}")
        
        # Clear connection tracking
        self.connection_users.clear()
        
        self._is_initialized = False
        logger.info("[MANAGER] Cleanup complete")

# Singleton instance
manager = ConnectionManager()