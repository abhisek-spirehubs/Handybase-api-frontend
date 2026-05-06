from typing import Optional, List, Dict


class AppException(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_code: str = "APP_ERROR",
        errors: Optional[List[Dict]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.errors = errors
        super().__init__(message)


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, 404, "NOT_FOUND")


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, 401, "UNAUTHORIZED")


class ForbiddenException(AppException):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, 403, "FORBIDDEN")


class ConflictException(AppException):
    def __init__(self, message: str = "Conflict"):
        super().__init__(message, 409, "CONFLICT")


class ValidationException(AppException):
    def __init__(
        self,
        message: str = "Validation failed",
        errors: Optional[List[Dict]] = None,
    ):
        # ✅ ensure frontend always gets structured errors
        if errors is None:
            errors = [{"field": None, "message": message}]

        super().__init__(
            message=message,
            status_code=422,
            error_code="INVALID_INPUT",
            errors=errors,
        )


class RateLimitException(AppException):
    def __init__(self, message: str = "Too many requests"):
        super().__init__(message, 429, "RATE_LIMIT_EXCEEDED")


class ServiceUnavailableException(AppException):
    def __init__(self, message: str = "Service temporarily unavailable"):
        super().__init__(message, 503, "SERVICE_UNAVAILABLE")