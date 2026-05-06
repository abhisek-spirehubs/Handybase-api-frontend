from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,   # 👈 use sync Redis (no async+)
    strategy="moving-window",          # sliding window
)


def login_rate_limit():
    # 5 requests per minute
    return limiter.limit("5/minute")


def register_rate_limit():
    # 3 requests per minute
    return limiter.limit("3/minute")


def send_otp_rate_limit():
    # 50 OTP requests per hour
    return limiter.limit("50/hour")


def verify_otp_rate_limit():
    # 5 attempts per 5 minutes
    return limiter.limit("5/5minutes")


def change_password_otp_rate_limit():
    """
    Rate limit for the final change-password-with-otp step.
    Protects against abuse after OTP verification. Default: 5 attempts per 10 minutes.
    """
    return limiter.limit("5/10minutes")
