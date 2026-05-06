from beanie import Document
from datetime import datetime, timezone
from pydantic import Field
from typing import Optional
from app.schemas.common import StatusEnum


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LogBase(Document):
    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    deleted_at: Optional[datetime] = None

    # Audit users
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    deleted_by: Optional[str] = None

    # Soft delete
    is_deleted: bool = False

    class Settings:
        use_state_management = True

    async def save(self, *args, **kwargs):
        """
        Override save to update timestamp automatically.
        """
        self.updated_at = utc_now()
        return await super().save(*args, **kwargs)

    async def soft_delete(self, user_id: Optional[str] = None):
        """
        Soft delete the document.
        """
        self.is_deleted = True
        self.deleted_at = utc_now()
        self.deleted_by = user_id
        await self.save()


class BaseLogWithStatus(LogBase):
    status: StatusEnum = Field(default=StatusEnum.ACTIVE)
