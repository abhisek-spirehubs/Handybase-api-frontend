import asyncio
from app.utils.logger import app_logger
from app.services.redis_chat_service import RedisChatService
from app.services.chat_service import ChatService
# ADD these imports at the top
from app.background_tasks.analytics_task import (
    periodic_analytics_refresh,
    periodic_booking_trend_aggregation,
    backfill_booking_trends,
)

async def periodic_redis_sync():
    """
    Periodic background task to sync Redis unread counts to MongoDB
    Runs every 5 minutes
    """
    while True:
        try:
            app_logger.info("Starting periodic Redis sync to MongoDB")
            await RedisChatService.sync_all_pending_rooms(ChatService)
            app_logger.info("Completed periodic Redis sync")
            asyncio.create_task(periodic_analytics_refresh())
            asyncio.create_task(periodic_booking_trend_aggregation())
            
            # Sleep for 5 minutes
            await asyncio.sleep(300)
            
        except Exception as e:
            app_logger.error(f"Error in periodic Redis sync: {str(e)}")
            await asyncio.sleep(60)  # Wait a minute and retry
            await backfill_booking_trends(days=30)