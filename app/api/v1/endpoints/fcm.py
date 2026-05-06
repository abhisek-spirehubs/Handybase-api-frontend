# app/api/v1/endpoints/fcm.py
from fastapi import APIRouter, Depends, BackgroundTasks
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.push_service import PushService
from app.schemas.fcm import TokenRegisterRequest, TokenRegisterResponse

router = APIRouter()

@router.post("/token/register", response_model=TokenRegisterResponse)
async def register_token(
    req: TokenRegisterRequest,
    current_user: User = Depends(get_current_user),
):
    await PushService.register_token(
        user_id=str(current_user.id),
        token=req.token,
        device_id=req.device_id,
        platform=req.platform,
    )
    return TokenRegisterResponse(success=True, message="Token registered")

@router.delete("/token/{token}", response_model=TokenRegisterResponse)
async def unregister_token(
    token: str,
    current_user: User = Depends(get_current_user),
):
    await PushService.deactivate_token(token)
    return TokenRegisterResponse(success=True, message="Token deactivated")

@router.delete("/tokens", response_model=TokenRegisterResponse)
async def unregister_all_tokens(
    current_user: User = Depends(get_current_user),
):
    await PushService.deactivate_all_tokens(str(current_user.id))
    return TokenRegisterResponse(success=True, message="All tokens deactivated")