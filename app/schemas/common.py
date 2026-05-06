from enum import Enum
from datetime import datetime
from pydantic import BaseModel
from typing import Generic, TypeVar, Optional, List

T = TypeVar("T")


# ── Enums ─────────────────────────────────────────────────────────────────────

class StatusEnum(str, Enum):
    ACTIVE   = "active"
    INACTIVE = "inactive"


# ── Standard Success Response ─────────────────────────────────────────────────

class APIResponse(BaseModel, Generic[T]):
    """
    Envelope for all single-object responses.
    Frontend always checks .success and reads from .data.
    """
    success: bool        = True
    message: str
    data:    Optional[T] = None


# ── Paginated Response ────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel, Generic[T]):
    """
    Envelope for all paginated list responses.
    Self-contained — not wrapped inside APIResponse.

    Frontend pagination contract:
      - success → always True
      - message → human-readable status
      - total   → total number of matching records across all pages
      - data    → list of items for the current page
    """
    success: bool    = True
    message: str
    total:   int
    data:    List[T]


# ── Message Response ──────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    """
    For endpoints that return no data object — only a status message.
    Examples: logout, change-password, send-otp.
    """
    success: bool = True
    message: str


# ── Delete Response ───────────────────────────────────────────────────────────

class DeleteResponse(BaseModel):
    """
    Returned by all soft-delete endpoints.

    Frontend contract:
      - id         → use to remove the item from local cache / list
      - deleted_at → show "deleted X ago" or power an undo window
      - deleted_by → audit trail; lets admin UI show who deleted it

    Never returns the full object — if the frontend needs the object
    it should have cached it before issuing the delete.
    """
    success:    bool     = True
    message:    str
    id:         str
    deleted_at: datetime
    deleted_by: str


# ── ID Response ───────────────────────────────────────────────────────────────

class IDResponse(BaseModel):
    """
    For create endpoints that only need to return the new resource's ID.
    Example: admin create user.
    """
    success: bool = True
    message: str
    id:      str


# ── Error Response ────────────────────────────────────────────────────────────

class APIErrorDetail(BaseModel):
    field:   Optional[str] = None
    message: str


class APIErrorResponse(BaseModel):
    """
    Standard error shape returned by all exception handlers.
    Frontend switches on error_code — never on message (messages may change).
    """
    success:    bool                           = False
    message:    str
    error_code: str
    errors:     Optional[List[APIErrorDetail]] = None


# ── Social Links ──────────────────────────────────────────────────────────────

class SocialLinks(BaseModel):
    """
    Typed social links — frontend can rely on exact field names.
    All fields optional; only send what the provider has set.
    """
    instagram: Optional[str] = None
    facebook:  Optional[str] = None
    twitter:   Optional[str] = None
    linkedin:  Optional[str] = None
    youtube:   Optional[str] = None