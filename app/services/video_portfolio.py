from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import UploadFile

from app.models.user import User
from app.core.exceptions import (
    ValidationException, NotFoundException, ForbiddenException, AppException,
)
from app.utils.logger import app_logger

MEDIA_ROOT      = "media"
VIDEO_FOLDER    = "providers/videos"
MAX_VIDEO_MB    = 100
ALLOWED_EXTS    = {"mp4", "mov", "avi", "mkv", "webm"}


def _video_url_to_path(url: str) -> str:
    return url.lstrip("/")


async def _save_video(file: UploadFile) -> str:
    """Save video to media/providers/videos/ and return URL."""
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTS:
        raise ValidationException(
            f"Unsupported video format '{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTS))}"
        )

    # Read content first so we can check size
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_VIDEO_MB:
        raise ValidationException(
            f"Video exceeds maximum size of {MAX_VIDEO_MB} MB "
            f"(uploaded: {size_mb:.1f} MB)"
        )

    folder_path = os.path.join(MEDIA_ROOT, VIDEO_FOLDER)
    os.makedirs(folder_path, exist_ok=True)

    filename  = f"{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(folder_path, filename)

    with open(file_path, "wb") as buf:
        buf.write(content)

    return f"/media/{VIDEO_FOLDER}/{filename}"


# ── Public service functions ──────────────────────────────────────────────────

async def upload_video(
    provider: User,
    file: UploadFile,
    title: Optional[str],
    description: Optional[str],
) -> dict:
    """
    Upload a new video to the provider's portfolio.
    Appends a video entry to User.portfolio_videos list (stored in users collection).
    No separate collection — keeps it simple and avoids extra DB overhead.
    """
    try:
        if not provider.is_provider_approved:
            raise ForbiddenException("Your provider account is not approved yet.")

        # Enforce a reasonable cap (e.g. 10 videos per provider)
        existing = provider.portfolio_videos or []
        if len(existing) >= 10:
            raise ValidationException(
                "You can upload a maximum of 10 portfolio videos. "
                "Delete an existing video to upload a new one."
            )

        url = await _save_video(file)

        video_entry = {
            "id":          uuid.uuid4().hex,
            "url":         url,
            "title":       title,
            "description": description,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }

        provider.portfolio_videos = existing + [video_entry]
        await provider.save()

        return video_entry

    except AppException:
        raise
    except Exception:
        app_logger.exception("Video upload failed provider_id=%s", str(provider.id))
        raise AppException("Failed to upload video", status_code=500)


async def list_videos(provider_id: str) -> List[dict]:
    """
    Return all portfolio videos for a provider.
    Called on public profile page — no auth required.
    """
    try:
        provider = await User.get(provider_id)
        if not provider or provider.is_deleted:
            raise NotFoundException("Provider not found")
        return provider.portfolio_videos or []
    except AppException:
        raise
    except Exception:
        app_logger.exception("List videos failed provider_id=%s", provider_id)
        raise AppException("Failed to fetch videos", status_code=500)


async def delete_video(provider: User, video_id: str) -> None:
    """
    Remove a video from the provider's portfolio and delete the file from disk.
    """
    try:
        existing = provider.portfolio_videos or []
        target   = next((v for v in existing if v["id"] == video_id), None)

        if not target:
            raise NotFoundException("Video not found in your portfolio")

        # Remove file from disk
        file_path = _video_url_to_path(target["url"])
        if os.path.exists(file_path):
            os.remove(file_path)

        provider.portfolio_videos = [v for v in existing if v["id"] != video_id]
        await provider.save()

    except AppException:
        raise
    except Exception:
        app_logger.exception(
            "Delete video failed provider_id=%s video_id=%s",
            str(provider.id), video_id,
        )
        raise AppException("Failed to delete video", status_code=500)