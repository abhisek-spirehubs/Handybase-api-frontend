from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
import os
import uvicorn
import asyncio

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# APScheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.middleware.logging import log_requests
from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection
from app.core.exceptions import AppException
from app.core.handlers import (
    app_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
)
from app.api.v1.router import api_router
from app.api.v1.sockets import chat_socket
from app.dependencies.rate_limit import limiter
from app.core.redis_client import RedisClient
from app.core.socket_manager import manager
from app.services.redis_chat_service import RedisChatService
from app.services.chat_service import ChatService
from app.utils.logger import app_logger
from app.core.firebase import init_firebase

logging.getLogger("motor").setLevel(logging.WARNING)
logging.getLogger("pymongo").setLevel(logging.WARNING)

# ── Background task references ────────────────────────────────────────────────
redis_sync_task = None
scheduler       = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown events."""

    # ── STARTUP ───────────────────────────────────────────────────────────────
    app_logger.info("=" * 60)
    app_logger.info("APPLICATION STARTING UP")
    app_logger.info("=" * 60)

    global redis_sync_task

    try:
        # MongoDB
        await connect_to_mongo()
        app_logger.info("MongoDB connected")

        # Firebase
        init_firebase(settings.FIREBASE_CREDENTIALS_PATH)
        app_logger.info("Firebase initialized")

        # Redis + PubSub
        await manager.initialize_redis()
        app_logger.info("Redis PubSub initialized")

        # ── APScheduler ───────────────────────────────────────────────────
        from app.services.subscription_service import SubscriptionService

        scheduler.add_job(
            SubscriptionService.expire_stale_subscriptions,
            trigger="cron",
            hour=0,
            minute=0,
            id="expire_subscriptions",
            replace_existing=True,
        )

        scheduler.add_job(
            SubscriptionService.warn_expiring_subscriptions,
            trigger="cron",
            hour=9,
            minute=0,
            id="warn_expiring_subscriptions",
            replace_existing=True,
        )

        scheduler.start()
        app_logger.info(
            "APScheduler started — "
            "expire_subscriptions at 00:00 | "
            "warn_expiring at 09:00"
        )
        # ─────────────────────────────────────────────────────────────────

        # Periodic Redis sync
        redis_sync_task = asyncio.create_task(periodic_redis_sync())
        app_logger.info("Periodic Redis sync task started")

        app_logger.info("All services initialized successfully")

    except Exception as e:
        app_logger.error("Startup failed: {}", str(e), exc_info=True)
        raise

    yield  # ── Application runs here ──────────────────────────────────────

    # ── SHUTDOWN ──────────────────────────────────────────────────────────────
    app_logger.info("=" * 60)
    app_logger.info("APPLICATION SHUTTING DOWN")
    app_logger.info("=" * 60)

    try:
        # Stop scheduler
        if scheduler.running:
            scheduler.shutdown(wait=False)
            app_logger.info("APScheduler stopped")

        # Cancel periodic Redis sync
        if redis_sync_task:
            redis_sync_task.cancel()
            try:
                await redis_sync_task
            except asyncio.CancelledError:
                app_logger.info("Periodic sync task cancelled")

        # Final Redis → MongoDB sync before shutdown
        app_logger.info("Performing final Redis sync to MongoDB...")
        try:
            await RedisChatService.sync_all_pending_rooms(ChatService)
            app_logger.info("Final Redis sync completed")
        except Exception as e:
            app_logger.error("Final Redis sync failed: {}", str(e))

        await close_mongo_connection()
        app_logger.info("MongoDB connection closed")

        await manager.cleanup()
        app_logger.info("Redis PubSub cleaned up")

        await RedisClient.close()
        app_logger.info("Redis client closed")

    except Exception as e:
        app_logger.error("Shutdown error: {}", str(e), exc_info=True)

    app_logger.info("Shutdown complete")


async def periodic_redis_sync():
    """
    Background task — syncs Redis unread counts to MongoDB every 5 minutes.
    """
    while True:
        try:
            await asyncio.sleep(300)
            app_logger.info("Starting periodic Redis sync to MongoDB")
            await RedisChatService.sync_all_pending_rooms(ChatService)
            app_logger.info("Completed periodic Redis sync")

        except asyncio.CancelledError:
            app_logger.info("Periodic Redis sync task cancelled")
            break
        except Exception as e:
            app_logger.error(
                "Error in periodic Redis sync: {}", str(e), exc_info=True
            )
            await asyncio.sleep(180)


# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="HandyBase API",
    version="1.0.0",
    description="""
## HandyBase — Skilled Hands. Trusted Service.

### Authentication
All protected endpoints require `Authorization: Bearer <token>` from `POST /auth/login`.

### User Roles
- **Client** — browse, book, chat, pay, review
- **Provider** — list services, manage bookings, availability calendar
- **Admin** — manage plans, approve providers, view all data

### Subscription Tiers
| Tier | Type | Features |
|---|---|---|
| Client Free | Client | Browse only |
| Client Paid | Client | Full access — book, chat, pay, review |
| Provider Tier 1 | Provider | Profile presence only |
| Provider Tier 2 | Provider | Services + calendar + payments |
| Provider Tier 3 | Provider | Analytics + reports + priority listing |

### Error Response Format
All errors return:
```json
{
  "success": false,
  "error": "Human readable message",
  "code": "MACHINE_READABLE_CODE"
}
```
    """,
    contact={
        "name":  "HandyBase Support",
        "email": "support@handybase.com",
    },
    lifespan=lifespan,
    docs_url="/docs"            if settings.DEBUG else None,
    redoc_url="/redoc"          if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# ── Rate limiting ─────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-API-Version"],
)

# ── Request logging ───────────────────────────────────────────────────────────
app.middleware("http")(log_requests)

# ── Exception handlers ────────────────────────────────────────────────────────
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(chat_socket.router, prefix=settings.API_V1_STR)

# ── Static files ──────────────────────────────────────────────────────────────
os.makedirs("media", exist_ok=True)
app.mount("/media", StaticFiles(directory="media"), name="media")


@app.get("/", include_in_schema=False)
async def root():
    return {
        "message": "Welcome to HandyBase API",
        "version": "1.0.0",
        "docs":    "/docs" if settings.DEBUG else "disabled",
        "status":  "running",
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENV == "local",
    )