"""
api/v1/endpoints/document_exchange.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Secure Document Exchange — attach files to chats and bookings.

Endpoints:
  POST  /chats/{booking_id}/documents          — upload doc to a chat
  GET   /chats/{booking_id}/documents          — list docs in a chat
  POST  /bookings/{booking_id}/documents       — upload doc to a booking
  GET   /bookings/{booking_id}/documents       — list docs on a booking
  DELETE /documents/{document_id}              — delete own document
"""
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, Path, Query, UploadFile, status
from pydantic import BaseModel, Field

from app.dependencies.auth import get_current_user
from app.dependencies.subscription import require_feature
from app.models.booking import Booking, BookingStatus
from app.models.chat_room import ChatRoom
from app.models.user import User, UserRole
from app.models.common import BaseLogWithStatus
from app.schemas.common import MessageResponse
from app.core.exceptions import (
    AppException, ForbiddenException, NotFoundException, ValidationException,
)
from app.utils.logger import app_logger

router = APIRouter(tags=["Secure Document Exchange"])

# ── Config ────────────────────────────────────────────────────────────────────

MEDIA_ROOT      = "media"
DOC_FOLDER      = "documents"
MAX_DOC_MB      = 20
ALLOWED_DOC_EXTS = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "txt", "csv", "jpg", "jpeg", "png", "zip",
}


# ── Inline Beanie document model (no separate file needed) ───────────────────

class SharedDocument(BaseLogWithStatus):
    """
    Tracks every document uploaded in the context of a chat or booking.
    The actual file lives on disk at /media/documents/{filename}.
    """
    uploader_id:  str
    context_type: str            # "chat" | "booking"
    context_id:   str            # booking_id (chat is 1-to-1 with booking)
    file_url:     str
    file_name:    str
    file_size_kb: int
    mime_type:    Optional[str] = None

    class Settings:
        name = "shared_documents"
        indexes = [
            [("context_type", 1), ("context_id", 1), ("is_deleted", 1)],
            [("uploader_id",  1), ("is_deleted", 1), ("created_at", -1)],
        ]


# ── Response schemas ──────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    id:           str
    uploader_id:  str
    context_type: str
    context_id:   str
    file_url:     str
    file_name:    str
    file_size_kb: int
    mime_type:    Optional[str] = None
    created_at:   datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    success: bool = True
    message: str
    total:   int
    data:    List[DocumentResponse] = Field(default_factory=list)


class DocumentUploadResponse(BaseModel):
    success: bool = True
    message: str
    data:    DocumentResponse


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _save_document(file: UploadFile) -> tuple[str, int]:
    """Save file to media/documents/, return (url, size_kb)."""
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_DOC_EXTS:
        raise ValidationException(
            f"Unsupported file type '.{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_DOC_EXTS))}"
        )

    content = await file.read()
    size_kb  = len(content) // 1024
    size_mb  = len(content) / (1024 * 1024)

    if size_mb > MAX_DOC_MB:
        raise ValidationException(
            f"File exceeds maximum size of {MAX_DOC_MB} MB "
            f"(uploaded: {size_mb:.1f} MB)"
        )

    folder = os.path.join(MEDIA_ROOT, DOC_FOLDER)
    os.makedirs(folder, exist_ok=True)

    filename  = f"{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(folder, filename)

    with open(file_path, "wb") as buf:
        buf.write(content)

    return f"/media/{DOC_FOLDER}/{filename}", size_kb


async def _assert_booking_participant(booking_id: str, user_id: str) -> Booking:
    """Raises if booking not found or user is not a participant."""
    if not ObjectId.is_valid(booking_id):
        raise ValidationException("Invalid booking id")

    booking = await Booking.get(booking_id)
    if not booking or booking.is_deleted:
        raise NotFoundException("Booking not found")

    if user_id not in [booking.client_id, booking.provider_id]:
        raise ForbiddenException("Not allowed — you are not a participant of this booking")

    return booking


async def _assert_chat_participant(booking_id: str, user_id: str) -> ChatRoom:
    """Raises if chat room not found or user is not a participant."""
    if not ObjectId.is_valid(booking_id):
        raise ValidationException("Invalid booking id")

    room = await ChatRoom.find_one(
        {"booking_id": booking_id, "is_deleted": False}
    )
    if not room:
        raise NotFoundException(
            "Chat room not found. Chat is only available for confirmed bookings."
        )

    if user_id not in [room.client_id, room.provider_id]:
        raise ForbiddenException("Not allowed")

    return room


def _doc_to_response(doc: SharedDocument) -> DocumentResponse:
    return DocumentResponse(
        id=str(doc.id),
        uploader_id=doc.uploader_id,
        context_type=doc.context_type,
        context_id=doc.context_id,
        file_url=doc.file_url,
        file_name=doc.file_name,
        file_size_kb=doc.file_size_kb,
        mime_type=doc.mime_type,
        created_at=doc.created_at,
    )


# ── Chat document endpoints ───────────────────────────────────────────────────

@router.post(
    "/chats/{booking_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document to a chat conversation (paid plan)",
)
async def upload_chat_document(
    booking_id:   str        = Path(...),
    file:         UploadFile = File(..., description=f"Max {MAX_DOC_MB} MB — pdf, docx, xlsx, jpg, png, zip, etc."),
    current_user: User       = Depends(require_feature("can_exchange_documents")),
):
    """
    Upload a document within a chat conversation.
    The document is linked to the booking's chat room.
    Both client and provider can upload and download.
    Booking must be CONFIRMED for chat to exist.
    """
    try:
        room = await _assert_chat_participant(booking_id, str(current_user.id))

        file_url, size_kb = await _save_document(file)

        doc = SharedDocument(
            uploader_id=str(current_user.id),
            context_type="chat",
            context_id=booking_id,
            file_url=file_url,
            file_name=file.filename or "document",
            file_size_kb=size_kb,
            mime_type=file.content_type,
            created_by=str(current_user.id),
        )
        await doc.insert()

        return {
            "success": True,
            "message": "Document uploaded successfully",
            "data":    _doc_to_response(doc),
        }

    except AppException:
        raise
    except Exception:
        app_logger.exception("Chat doc upload failed booking_id=%s", booking_id)
        raise AppException("Failed to upload document", status_code=500)


@router.get(
    "/chats/{booking_id}/documents",
    response_model=DocumentListResponse,
    summary="List documents shared in a chat (both participants)",
)
async def list_chat_documents(
    booking_id:   str  = Path(...),
    page:         int  = Query(1, ge=1),
    limit:        int  = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    try:
        await _assert_chat_participant(booking_id, str(current_user.id))

        skip  = (page - 1) * limit
        query = [
            SharedDocument.context_type == "chat",
            SharedDocument.context_id   == booking_id,
            SharedDocument.is_deleted   == False,
        ]
        total = await SharedDocument.find(*query).count()
        docs  = (
            await SharedDocument.find(*query)
            .sort("-created_at").skip(skip).limit(limit).to_list()
        )

        return {
            "success": True,
            "message": "Documents fetched successfully",
            "total":   total,
            "data":    [_doc_to_response(d) for d in docs],
        }

    except AppException:
        raise
    except Exception:
        app_logger.exception("List chat docs failed booking_id=%s", booking_id)
        raise AppException("Failed to fetch documents", status_code=500)


# ── Booking document endpoints ────────────────────────────────────────────────

@router.post(
    "/bookings/{booking_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document to a booking (paid plan)",
)
async def upload_booking_document(
    booking_id:   str        = Path(...),
    file:         UploadFile = File(..., description=f"Max {MAX_DOC_MB} MB — pdf, docx, xlsx, jpg, png, zip, etc."),
    current_user: User       = Depends(require_feature("can_exchange_documents")),
):
    """
    Attach a job-related document directly to a booking.
    Useful for contracts, invoices, permits, or job specs.
    Both client and provider can upload.
    """
    try:
        await _assert_booking_participant(booking_id, str(current_user.id))

        file_url, size_kb = await _save_document(file)

        doc = SharedDocument(
            uploader_id=str(current_user.id),
            context_type="booking",
            context_id=booking_id,
            file_url=file_url,
            file_name=file.filename or "document",
            file_size_kb=size_kb,
            mime_type=file.content_type,
            created_by=str(current_user.id),
        )
        await doc.insert()

        return {
            "success": True,
            "message": "Document uploaded successfully",
            "data":    _doc_to_response(doc),
        }

    except AppException:
        raise
    except Exception:
        app_logger.exception("Booking doc upload failed booking_id=%s", booking_id)
        raise AppException("Failed to upload document", status_code=500)


@router.get(
    "/bookings/{booking_id}/documents",
    response_model=DocumentListResponse,
    summary="List documents attached to a booking (both participants)",
)
async def list_booking_documents(
    booking_id:   str  = Path(...),
    page:         int  = Query(1, ge=1),
    limit:        int  = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    try:
        await _assert_booking_participant(booking_id, str(current_user.id))

        skip  = (page - 1) * limit
        query = [
            SharedDocument.context_type == "booking",
            SharedDocument.context_id   == booking_id,
            SharedDocument.is_deleted   == False,
        ]
        total = await SharedDocument.find(*query).count()
        docs  = (
            await SharedDocument.find(*query)
            .sort("-created_at").skip(skip).limit(limit).to_list()
        )

        return {
            "success": True,
            "message": "Documents fetched successfully",
            "total":   total,
            "data":    [_doc_to_response(d) for d in docs],
        }

    except AppException:
        raise
    except Exception:
        app_logger.exception("List booking docs failed booking_id=%s", booking_id)
        raise AppException("Failed to fetch documents", status_code=500)


# ── Delete a document ─────────────────────────────────────────────────────────

@router.delete(
    "/documents/{document_id}",
    response_model=MessageResponse,
    summary="Delete a document (uploader only)",
)
async def delete_document(
    document_id:  str  = Path(...),
    current_user: User = Depends(get_current_user),
):
    """
    Soft-deletes the document record and removes the file from disk.
    Only the uploader can delete their own documents.
    """
    try:
        if not ObjectId.is_valid(document_id):
            raise ValidationException("Invalid document id")

        doc = await SharedDocument.get(document_id)
        if not doc or doc.is_deleted:
            raise NotFoundException("Document not found")

        if doc.uploader_id != str(current_user.id):
            raise ForbiddenException("You can only delete your own documents")

        # Remove file from disk
        file_path = doc.file_url.lstrip("/")
        if os.path.exists(file_path):
            os.remove(file_path)

        await doc.soft_delete(str(current_user.id))

        return {"success": True, "message": "Document deleted successfully"}

    except AppException:
        raise
    except Exception:
        app_logger.exception("Delete doc failed document_id=%s", document_id)
        raise AppException("Failed to delete document", status_code=500)