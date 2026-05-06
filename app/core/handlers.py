from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.exceptions import AppException
from app.utils.logger import app_logger


# ── AppException handler ─────────────────────────────────────────

async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.message,
            "error_code": exc.error_code,
            "errors": exc.errors,
        },
    )


# ── Validation error handler ─────────────────────────────────────

async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:

    errors = []

    for err in exc.errors():
        loc = err.get("loc", [])

        # ✅ clean field path (no body/query/path noise)
        field = ".".join(
            str(x) for x in loc
            if x not in ("body", "query", "path")
        )

        errors.append({
            "field": field or None,
            "message": err.get("msg", "Invalid value"),
        })

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Validation failed",
            "error_code": "INVALID_INPUT",
            "errors": errors,
        },
    )


# ── Generic exception handler ────────────────────────────────────

async def generic_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:

    request_id = getattr(request.state, "request_id", "unknown")

    app_logger.error(
        "Unhandled error [request_id={}]: {}",
        request_id,
        exc,
        exc_info=True,
    )

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "error_code": "INTERNAL_ERROR",
            "errors": None,
        },
    )