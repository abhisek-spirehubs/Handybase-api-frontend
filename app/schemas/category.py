from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List
from datetime import datetime

from app.schemas.base import MongoBaseResponse
from app.schemas.common import StatusEnum


# ── Request schemas ───────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    name:        str
    description: Optional[str] = None
    parent_id:   Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()


class CategoryUpdate(BaseModel):
    name:        Optional[str]        = None
    description: Optional[str]        = None
    parent_id:   Optional[str]        = None
    status:      Optional[StatusEnum] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip() if v else v

    @model_validator(mode="after")
    def at_least_one_field(self) -> "CategoryUpdate":
        if not any(v is not None for v in self.model_dump(exclude_unset=True).values()):
            raise ValueError("At least one field must be provided for update")
        return self


class CategoryStatusUpdate(BaseModel):
    status: StatusEnum


# ── Response schemas ──────────────────────────────────────────────────────────

class CategoryResponse(MongoBaseResponse):
    """
    Single category data object.
    Extends MongoBaseResponse — _id → id conversion handled in base.
    Always wrapped in APIResponse[CategoryResponse] or PaginatedResponse[CategoryResponse].
    Never returned naked.
    """
    name:        str
    slug:        Optional[str]        = None
    icon:        Optional[str]        = None
    description: Optional[str]        = None
    parent_id:   Optional[str]        = None
    status:      StatusEnum
    created_at:  datetime
    updated_at:  Optional[datetime]   = None


class CategoryTreeResponse(CategoryResponse):
    """
    Used when the frontend needs a nested tree (e.g. sidebar nav).
    Children are populated server-side — frontend does not need to
    make recursive calls.
    """
    children: List["CategoryTreeResponse"] = Field(default_factory=list)


CategoryTreeResponse.model_rebuild()
