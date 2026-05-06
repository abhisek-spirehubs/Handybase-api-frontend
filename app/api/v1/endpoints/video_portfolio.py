"""
api/v1/endpoints/video_portfolio.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Provider video portfolio endpoints.

  POST   /providers/me/portfolio/videos          — upload a video
  GET    /providers/{provider_id}/portfolio/videos — public list
  DELETE /providers/me/portfolio/videos/{video_id} — delete own video
"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Path, UploadFile, status

from app.dependencies.auth import get_current_user
from app.dependencies.subscription import require_feature
from app.models.user import User, UserRole
from app.schemas.video_portfolio import (
    VideoPortfolioResponse,
    VideoUploadResponse,
   
)

from app.schemas.common import MessageResponse
from app.services import video_portfolio
from app.core.exceptions import ForbiddenException

router = APIRouter()


# ── Upload ────────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=VideoUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a portfolio video (Tier 3 provider)",
)
async def upload_portfolio_video(
    file:        UploadFile  = File(..., description="Video file — mp4, mov, avi, mkv, webm"),
    title:       Optional[str] = Form(None, max_length=100),
    description: Optional[str] = Form(None, max_length=500),
    current_user: User = Depends(require_feature("can_upload_videos")),
):
    """
    Upload a video to the authenticated provider's portfolio.
    Max 100 MB per file. Max 10 videos total.
    """
    if current_user.user_type != UserRole.PROVIDER:
        raise ForbiddenException("Only providers can upload portfolio videos.")

    video_entry = await video_portfolio.upload_video(
        provider=current_user,
        file=file,
        title=title,
        description=description,
    )

    return {
        "success": True,
        "message": "Video uploaded successfully",
        "data":    video_entry,
    }


# ── Public list ───────────────────────────────────────────────────────────────

@router.get(
    "/{provider_id}",
    response_model=VideoPortfolioResponse,
    summary="Get provider portfolio videos",
)
async def get_portfolio_videos(
    provider_id: str = Path(..., description="Provider user ID"),
    current_user: User = Depends(get_current_user),
):
    """
    Access rules:
    - CLIENT → any provider
    - ADMIN → any provider
    - PROVIDER → only own videos
    """

    # ❌ Provider trying to access others' videos
    if current_user.user_type == UserRole.PROVIDER:
        if str(current_user.id) != provider_id:
            raise ForbiddenException("Providers can only view their own portfolio videos.")

    # ❌ Any other role (if exists)
    elif current_user.user_type not in [UserRole.CLIENT, UserRole.ADMIN]:
        raise ForbiddenException("Not allowed to view portfolio videos.")

    videos = await video_portfolio.list_videos(provider_id=provider_id)

    return {
        "success": True,
        "message": "Portfolio videos fetched successfully",
        "data": videos,
    }


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete(
    "{video_id}",
    response_model=MessageResponse,
    summary="Delete own portfolio video (provider)",
)
async def delete_portfolio_video(
    video_id:     str  = Path(..., description="Video ID to delete"),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a video from the authenticated provider's portfolio.
    File is removed from disk immediately.
    """
    if current_user.user_type != UserRole.PROVIDER:
        raise ForbiddenException("Only providers can delete portfolio videos.")

    await video_portfolio.delete_video(
        provider=current_user,
        video_id=video_id,
    )

    return {
        "success": True,
        "message": "Video deleted successfully",
    }