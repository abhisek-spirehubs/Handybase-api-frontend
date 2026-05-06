from fastapi import APIRouter, Depends, status, Request

from app.services.auth_service import AuthService
from app.dependencies.rate_limit import (
    login_rate_limit,
    verify_otp_rate_limit,
    send_otp_rate_limit,
    change_password_otp_rate_limit,
)
from app.dependencies.auth import get_current_user, admin_required
from app.models.user import User

from app.schemas.auth import (
    TokenResponse,
    SendOTPRequest,
    VerifyOTPRequest,
    ChangePasswordRequest,
    ChangePasswordWithOtpRequest,
    FCMTokenRequest,
    UserLogin,
    UserDataResponse,
    UpdateProfileRequest,
)

from app.schemas.common import APIResponse, MessageResponse, IDResponse
from app.schemas.admin import AdminCreateUser

router = APIRouter()


# ── Login ──────────────────────────────────────────────────────────────────────
@router.post(
    "/login",
    response_model=APIResponse[TokenResponse],
)
@login_rate_limit()
async def login(request: Request, data: UserLogin):
    token = await AuthService.login(data)

    return {
        "success": True,
        "message": "Login successful",
        "data":    token,
    }


# ── Logout ─────────────────────────────────────────────────────────────────────
@router.post(
    "/logout",
    response_model=MessageResponse,
)
async def logout(current_user: User = Depends(get_current_user)):
    # Business logic (FCM clear, audit, token blacklist) lives in service — not here
    await AuthService.logout(current_user)

    return {
        "success": True,
        "message": "Logged out successfully",
    }


# ── Admin create user ──────────────────────────────────────────────────────────
@router.post(
    "/users",
    response_model=IDResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_by_admin(
    data:  AdminCreateUser,
    admin: User = Depends(admin_required),
):
    # Service returns IDResponse-shaped dict including required `message` field
    return await AuthService.admin_create_user(data)


# ── Get current user ───────────────────────────────────────────────────────────
@router.get(
    "/me",
    response_model=APIResponse[UserDataResponse],
)
async def get_me(current_user: User = Depends(get_current_user)):
    # Service returns UserDataResponse — router owns the envelope
    user = await AuthService.get_me(current_user)

    return {
        "success": True,
        "message": "User fetched successfully",
        "data":    user,
    }


# ── Update profile ─────────────────────────────────────────────────────────────
@router.put(
    "/profile",
    response_model=APIResponse[UserDataResponse],
)
async def update_profile(
    data:         UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
):
    # Service returns UserDataResponse — router owns the envelope
    user = await AuthService.update_profile(
        user=current_user,
        data=data.model_dump(exclude_none=True),
    )

    return {
        "success": True,
        "message": "Profile updated successfully",
        "data":    user,
    }


# ── Change password ────────────────────────────────────────────────────────────
@router.patch(
    "/change-password",
    response_model=MessageResponse,
)
async def change_password(
    data:         ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
):
    # Service is void — router owns the envelope
    await AuthService.change_password(
        user=current_user,
        old_password=data.old_password,
        new_password=data.new_password,
    )

    return {
        "success": True,
        "message": "Password changed successfully",
    }


# ── Register FCM token ─────────────────────────────────────────────────────────
@router.post(
    "/fcm-token",
    response_model=MessageResponse,
)
async def register_fcm_token(
    data:         FCMTokenRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Registers the device FCM push token for the current user.
    Call this after login on the mobile client.
    """
    current_user.fcm_token  = data.token
    current_user.updated_by = str(current_user.id)
    await current_user.save()

    return {
        "success": True,
        "message": "FCM token registered successfully",
    }


# ── Send OTP ───────────────────────────────────────────────────────────────────
@router.post(
    "/send-otp",
    response_model=MessageResponse,
)
@send_otp_rate_limit()
async def send_otp(request: Request, data: SendOTPRequest):
    # CRITICAL: forward the service return directly — do NOT replace the message.
    # The service uses an anti-enumeration message ("If an account exists...")
    # that intentionally avoids confirming whether an email is registered.
    # Replacing it with "OTP sent successfully" leaks email existence.
    return await AuthService.send_otp(data.email)


# ── Verify OTP ─────────────────────────────────────────────────────────────────
@router.post(
    "/verify-otp",
    response_model=MessageResponse,
)
@verify_otp_rate_limit()
async def verify_otp(request: Request, data: VerifyOTPRequest):
    # Service is void — router owns the envelope
    await AuthService.verify_otp(
        email=data.email,
        otp=data.otp,
    )

    return {
        "success": True,
        "message": "OTP verified successfully",
    }


# ── Reset password with OTP ────────────────────────────────────────────────────
@router.post(
    "/change-password-with-otp",
    response_model=MessageResponse,
)
@change_password_otp_rate_limit()
async def change_password_with_otp(
    request: Request,
    data:    ChangePasswordWithOtpRequest,
):
    # Service is void — router owns the envelope
    await AuthService.change_password_with_otp(
        email=data.email,
        new_password=data.new_password,
    )

    return {
        "success": True,
        "message": "Password reset successfully",
    }