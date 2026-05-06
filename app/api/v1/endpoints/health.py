from datetime import datetime
from fastapi import APIRouter
from app.core.config import settings
from app.core.redis_client import RedisClient
from app.core.socket_manager import manager
from app.models.user import User

router = APIRouter()


@router.get(
    "",
    summary="Health check — returns service status",
    tags=["Health"],
)
async def health_check():
    """
    Returns current health status of all services.
    Used by load balancers, monitoring tools, and DevOps pipelines.
    """
    health = {
        "success":     True,
        "status":      "healthy",
        "version":     "1.0.0",
        "environment": settings.ENV,
        "timestamp":   datetime.utcnow().isoformat(),
        "services": {
            "api":     "up",
            "mongodb": "unknown",
            "redis":   "unknown",
        },
    }

    # ── MongoDB check ─────────────────────────────────────────────────
    try:
        await User.find_one()
        health["services"]["mongodb"] = "up"
    except Exception:
        health["services"]["mongodb"] = "down"
        health["status"]              = "unhealthy"
        health["success"]             = False

    # ── Redis check ───────────────────────────────────────────────────
    try:
        redis = await RedisClient.get_instance()
        await redis.ping()
        health["services"]["redis"] = "up"
    except Exception:
        health["services"]["redis"] = "down"
        health["status"]            = "degraded"   # Redis down = degraded not unhealthy

    return health


@router.get(
    "/redis-stats",
    summary="Redis stats — non-production only",
    tags=["Health"],
    include_in_schema=settings.DEBUG,   # hidden in production swagger
)
async def redis_stats():
    """
    Debug endpoint — Redis memory and connection stats.
    Not available in production.
    """
    if settings.ENV == "production":
        return {
            "success": False,
            "error":   "Not available in production",
            "code":    "FORBIDDEN",
        }

    try:
        redis = await RedisClient.get_instance()
        info  = await redis.info()
        return {
            "success": True,
            "data": {
                "used_memory":              info.get("used_memory_human", "N/A"),
                "connected_clients":        info.get("connected_clients", "N/A"),
                "total_commands_processed": info.get("total_commands_processed", "N/A"),
                "uptime_in_seconds":        info.get("uptime_in_seconds", "N/A"),
            },
        }
    except Exception as e:
        return {
            "success": False,
            "error":   str(e),
            "code":    "REDIS_ERROR",
        }