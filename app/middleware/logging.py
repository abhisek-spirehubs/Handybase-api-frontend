import time
import uuid
from fastapi import Request
from fastapi.responses import JSONResponse
from app.utils.logger import app_logger


async def log_requests(request: Request, call_next):
    if request.headers.get("upgrade", "").lower() == "websocket":
        return await call_next(request)

    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    start_time = time.time()

    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000
        app_logger.error(
            "[{}] {} {} UNHANDLED time={:.2f}ms error={}",
            request_id,
            request.method,
            request.url.path,
            duration_ms,
            exc,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error":   "Internal server error",
                "code":    "INTERNAL_ERROR",
            },
            headers={
                "X-Request-ID":  request_id,
                "X-API-Version": "1.0.0",
            },
        )

    duration_ms = (time.time() - start_time) * 1000
    app_logger.info(
        "[{}] {} {} status={} time={:.2f}ms",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )

    response.headers["X-Request-ID"]  = request_id
    response.headers["X-API-Version"] = "1.0.0"

    return response