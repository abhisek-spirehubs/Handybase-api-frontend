import hashlib
import random
import time
from datetime import datetime, timezone

from app.core.exceptions import (
    NotFoundException,
    UnauthorizedException,
    ForbiddenException,
    ConflictException,
    ValidationException,
    AppException,
)
from app.models.user import User, UserStatus, UserRole
from app.schemas.auth import UserDataResponse
from app.core.security import hash_password, verify_password, create_access_token
from app.utils.email import send_mail
from app.utils.logger import app_logger


OTP_EXPIRY_SECONDS          = 300   # 5 minutes
OTP_VERIFIED_EXPIRY_SECONDS = 600   # 10 minutes — window to reset password after OTP verified

# Whitelist of fields allowed in profile update.
# Prevents overwriting sensitive fields like user_type, password, email, etc.
ALLOWED_PROFILE_FIELDS = {
    "fname", "lname", "phone", "date_of_birth", "avatar_url"
}


def _hash_otp(otp: int) -> str:
    return hashlib.sha256(str(otp).encode()).hexdigest()


def _build_user_data(user: User) -> UserDataResponse:
    """Convert User document → UserDataResponse schema."""
    return UserDataResponse.model_validate(user, from_attributes=True)


class AuthService:

    # ─────────────────────────────────────────
    # Login
    # ─────────────────────────────────────────

    @staticmethod
    async def login(data) -> dict:
        """
        Returns TokenResponse-shaped dict.
        Router wraps it in APIResponse[TokenResponse].
        """
        user = await User.find_one(User.email == data.email)

        # Guard against None password (OAuth or admin-created accounts)
        if not user or not user.password or not verify_password(data.password, user.password):
            raise UnauthorizedException("Invalid email or password")

        if user.is_deleted:
            raise ForbiddenException("Account deleted")

        if user.status != UserStatus.ACTIVE:
            raise ForbiddenException("Account inactive")

        if not user.email_verified:
            raise ForbiddenException("Email not verified")

        if user.user_type == UserRole.PROVIDER and not user.is_provider_approved:
            raise ForbiddenException("Provider account not approved yet")

        user.last_login = datetime.now(timezone.utc)
        await user.save()

        token = create_access_token({
            "sub":  str(user.id),
            "role": user.user_type.value,
        })

        return {
            "access_token": token,
            "token_type":   "bearer",
        }

    # ─────────────────────────────────────────
    # Logout
    # ─────────────────────────────────────────

    @staticmethod
    async def logout(user: User) -> None:
        """
        Clears FCM token on logout.
        Extend here for token blacklisting or audit logging — never in the router.
        """
        user.fcm_token  = None
        user.updated_by = str(user.id)
        await user.save()

    # ─────────────────────────────────────────
    # Admin create user
    # ─────────────────────────────────────────

    @staticmethod
    async def admin_create_user(data) -> dict:
        """
        Returns IDResponse-shaped dict.
        Router uses IDResponse as response_model.
        """
        if data.user_type == UserRole.ADMIN:
            raise ValidationException("Cannot create admin through API")

        if await User.find_one(User.email == data.email):
            raise ConflictException("Email already registered")

        user = User(
            fname=data.fname,
            lname=data.lname,
            full_name=f"{data.fname} {data.lname}",
            email=data.email,
            password=hash_password(data.password),
            phone=data.phone,
            user_type=data.user_type,
            status=UserStatus.ACTIVE,
            email_verified=True,
            is_provider_approved=False,
        )

        await user.insert()

        try:
            await send_mail(
                {"to": user.email, "subject": "Your HandyBase account"},
                {
                    "fname":             user.fname or "User",
                    "email":             user.email,
                    "userRegisteration": True,
                },
                "email-template.html",
            )
        except Exception as e:
            app_logger.error("Admin user email failed: {}", e)

        # Return IDResponse-shaped dict — message field required by IDResponse schema
        return {
            "success": True,
            "message": "User created successfully",
            "id":      str(user.id),
        }

    # ─────────────────────────────────────────
    # Get me
    # ─────────────────────────────────────────

    @staticmethod
    async def get_me(user: User) -> UserDataResponse:
        """
        Returns the data object only.
        Router is responsible for the APIResponse envelope.
        """
        return _build_user_data(user)

    # ─────────────────────────────────────────
    # Update profile
    # ─────────────────────────────────────────

    @staticmethod
    async def update_profile(user: User, data: dict) -> UserDataResponse:
        """
        Returns the updated data object only.
        Router is responsible for the APIResponse envelope.
        """
        try:
            for field, value in data.items():
                if field in ALLOWED_PROFILE_FIELDS:
                    setattr(user, field, value)

            # Auto-update full_name if fname or lname changed
            if "fname" in data or "lname" in data:
                fname    = user.fname or ""
                lname    = user.lname or ""
                combined = f"{fname} {lname}".strip()
                if combined:
                    user.full_name = combined

            user.updated_by = str(user.id)
            await user.save()

            return _build_user_data(user)

        except Exception:
            app_logger.exception(
                "Failed to update profile user_id=%s", str(user.id)
            )
            raise AppException("Failed to update profile", status_code=500)

    # ─────────────────────────────────────────
    # Change password (logged in)
    # ─────────────────────────────────────────

    @staticmethod
    async def change_password(
        user:         User,
        old_password: str,
        new_password: str,
    ) -> None:
        """
        Void — router owns the MessageResponse envelope.
        Raises ValidationException on bad input; AppException on failure.
        """
        try:
            if not verify_password(old_password, user.password):
                raise ValidationException("Current password is incorrect")

            if old_password == new_password:
                raise ValidationException(
                    "New password must be different from current password"
                )

            user.password   = hash_password(new_password)
            user.updated_by = str(user.id)
            await user.save()

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to change password user_id=%s", str(user.id)
            )
            raise AppException("Failed to change password", status_code=500)

    # ─────────────────────────────────────────
    # Send OTP
    # ─────────────────────────────────────────

    @staticmethod
    async def send_otp(email: str) -> dict:
        """
        Returns a MessageResponse-shaped dict.
        IMPORTANT: uses anti-enumeration message regardless of whether
        the email exists — router must forward this exact message, not replace it.
        """
        email = email.strip().lower()
        user  = await User.find_one(User.email == email)

        # Never reveal whether email exists — prevents user enumeration attacks
        if not user or user.is_deleted or user.status != UserStatus.ACTIVE:
            return {
                "success": True,
                "message": "If an account exists, an OTP has been sent",
            }

        otp = random.randint(100000, 999999)

        user.otp_code        = _hash_otp(otp)
        user.otp_expire      = int(time.time()) + OTP_EXPIRY_SECONDS
        user.otp_verified    = False
        user.otp_verified_at = None

        await user.save()

        try:
            await send_mail(
                {"to": user.email, "subject": "Your OTP Code"},
                {
                    "fname":   user.fname or "User",
                    "otpCode": otp,
                    "sendOtp": True,
                },
                "email-template.html",
            )
        except Exception as e:
            app_logger.error("OTP email failed for {}: {}", user.email, e)

        return {
            "success": True,
            "message": "If an account exists, an OTP has been sent",
        }

    # ─────────────────────────────────────────
    # Verify OTP
    # ─────────────────────────────────────────

    @staticmethod
    async def verify_otp(email: str, otp: str) -> None:
        """
        Void — router owns the MessageResponse envelope.
        Raises appropriate AppException subclasses on failure.
        """
        email = email.strip().lower()
        user  = await User.find_one(User.email == email)

        if not user:
            raise NotFoundException("User not found")

        # Guard against suspended/deleted accounts using OTP flows
        if user.is_deleted:
            raise ForbiddenException("Account not accessible")

        if not user.otp_code:
            raise ValidationException("OTP not requested")
        if not user.otp_expire or user.otp_expire < int(time.time()):
            raise ValidationException("OTP expired")

        try:
            otp_int = int(otp)
        except ValueError:
            raise ValidationException("Invalid OTP format")

        if user.otp_code != _hash_otp(otp_int):
            raise ValidationException("Invalid OTP")

        user.otp_verified    = True
        user.otp_verified_at = int(time.time())
        # Only mark email_verified if not already verified (avoids redundant write on password-reset flow)
        if not user.email_verified:
            user.email_verified = True
        user.otp_code   = None
        user.otp_expire = None

        await user.save()

    # ─────────────────────────────────────────
    # Change password with OTP
    # ─────────────────────────────────────────

    @staticmethod
    async def change_password_with_otp(email: str, new_password: str) -> None:
        """
        Void — router owns the MessageResponse envelope.
        Requires OTP to have been verified via /verify-otp first.
        """
        email = email.strip().lower()
        user  = await User.find_one(User.email == email, User.is_deleted == False)

        if not user:
            raise NotFoundException("User not found")
        if not user.otp_verified:
            raise ValidationException("OTP not verified")

        now = int(time.time())
        if not user.otp_verified_at or (now - user.otp_verified_at) > OTP_VERIFIED_EXPIRY_SECONDS:
            user.otp_verified    = False
            user.otp_verified_at = None
            await user.save()
            raise ValidationException("Verification window expired. Request a new OTP.")

        user.password        = hash_password(new_password)
        user.otp_code        = None
        user.otp_expire      = None
        user.otp_verified    = False
        user.otp_verified_at = None
        # updated_at set automatically by LogBase.save()

        await user.save()

        try:
            await send_mail(
                {"to": user.email, "subject": "Password Reset Successful"},
                {"fname": user.fname or "User", "forgetPassword": True},
                "email-template.html",
            )
        except Exception as e:
            app_logger.error("Password reset email failed: {}", e)