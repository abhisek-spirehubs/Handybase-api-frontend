import redis.asyncio as aioredis
from typing import Optional
from app.core.config import settings
from app.utils.logger import app_logger

class RedisClient:
    _instance: Optional[aioredis.Redis] = None

    @classmethod
    async def get_instance(cls) -> aioredis.Redis:
        if cls._instance is None:
            try:
                app_logger.info(f"Connecting to Redis at {settings.redis_url}")
                cls._instance = await aioredis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    encoding="utf-8"
                )
                await cls._instance.ping()
                app_logger.info("Redis connected successfully")
            except Exception as e:
                app_logger.error(f"Redis connection failed: {str(e)}")
                raise
        return cls._instance

    @classmethod
    async def close(cls):
        if cls._instance:
            await cls._instance.close()
            cls._instance = None
            app_logger.info("Redis connection closed")

async def get_redis() -> aioredis.Redis:
    return await RedisClient.get_instance()