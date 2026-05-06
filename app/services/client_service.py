import re
from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import UploadFile
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
    AppException,
)
from app.core.security import hash_password
from app.models.user import User, UserRole, UserStatus
from app.schemas.client import ClientRegister, ClientDataResponse
from app.utils.email import send_mail
from app.utils.file_upload import delete_file, save_file
from app.utils.logger import app_logger


class UserService:

    # ─────────────────────────────────────────
    # Registration
    # ─────────────────────────────────────────

    @staticmethod
    async def register_client(data: ClientRegister) -> ClientDataResponse:
        """
        Returns ClientDataResponse only.
        Router is responsible for the APIResponse envelope.
        """
        if await User.find_one(User.email == data.email):
            raise ConflictException("Email already registered")

        try:
            user = User(
                email=data.email,
                password=hash_password(data.password),
                fname=data.fname,
                lname=data.lname,
                full_name=f"{data.fname or ''} {data.lname or ''}".strip() or None,
                phone=data.phone,
                date_of_birth=data.date_of_birth,
                avatar_url=data.avatar_url,
                user_type=UserRole.CLIENT,
                email_verified=False,
                status=UserStatus.ACTIVE,
            )
        except PydanticValidationError as e:
            first = e.errors()[0]
            field = " -> ".join(str(loc) for loc in first.get("loc", []))
            msg   = first.get("msg", "Invalid value")
            raise ValidationException(f"{field}: {msg}" if field else msg)

        await user.insert()

        # Assign free client plan — never blocks registration on failure
        try:
            from app.services.subscription_service import SubscriptionService
            await SubscriptionService.assign_free_plan(
                user_id=str(user.id),
                user_type=user.user_type,
            )
        except Exception as e:
            app_logger.error(
                "Failed to assign free plan on client registration user_id=%s: %s",
                str(user.id), e,
            )

        # Welcome email — never blocks registration on failure
        try:
            await send_mail(
                {"to": user.email, "subject": "Welcome to Handybase"},
                {
                    "fname":             user.fname or user.full_name or "User",
                    "email":             user.email,
                    "userRegisteration": True,
                },
                "email-template.html",
            )
        except Exception as e:
            app_logger.error("Client registration email failed: %s", e)

        return _build_client_data(user)

    # ─────────────────────────────────────────
    # Self-service
    # ─────────────────────────────────────────

    @staticmethod
    async def get_me(user: User) -> ClientDataResponse:
        """
        Returns ClientDataResponse only.
        Router is responsible for the APIResponse envelope.
        """
        return _build_client_data(user)

    @staticmethod
    async def update_client_profile(
        user_id:       str,
        fname:         Optional[str],
        lname:         Optional[str],
        phone:         Optional[str],
        date_of_birth: Optional[str],
        avatar:        Optional[UploadFile],
    ) -> ClientDataResponse:
        """
        Returns ClientDataResponse only.
        Router is responsible for the APIResponse envelope.
        """
        try:
            user = await UserService._get_active_client(user_id)

            if fname is not None:
                user.fname = fname.strip()
            if lname is not None:
                user.lname = lname.strip()
            if phone is not None:
                user.phone = phone

            if date_of_birth is not None:
                try:
                    user.date_of_birth = datetime.fromisoformat(date_of_birth)
                except ValueError:
                    raise ValidationException(
                        "Invalid date format. Use ISO format (YYYY-MM-DD)"
                    )

            # Recompute full_name whenever either name part changes
            if fname is not None or lname is not None:
                user.full_name = (
                    f"{user.fname or ''} {user.lname or ''}".strip() or None
                )

            if avatar:
                if avatar.content_type not in ("image/jpeg", "image/png", "image/webp"):
                    raise ValidationException("Avatar must be JPEG, PNG, or WebP")
                if user.avatar_url:
                    delete_file(user.avatar_url)
                user.avatar_url = await save_file(avatar, "avatars")

            user.updated_by = user_id
            await user.save()

            return _build_client_data(user)

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to update client profile user_id=%s", user_id)
            raise AppException("Failed to update profile", status_code=500)

    # ─────────────────────────────────────────
    # Admin
    # ─────────────────────────────────────────

    @staticmethod
    async def get_client_by_id(client_id: str) -> ClientDataResponse:
        """
        Returns ClientDataResponse only.
        Router is responsible for the APIResponse envelope.
        """
        user = await UserService._get_active_client(client_id)
        return _build_client_data(user)

    @staticmethod
    async def get_all_clients(
        page:   int,
        limit:  int,
        search: Optional[str],
        status: Optional[str],
    ) -> dict:
        """
        Returns PaginatedResponse-shaped dict: success, message, total, data.
        Router returns this directly — it is already the full response.
        """
        try:
            skip = (page - 1) * limit
            query: dict = {
                "is_deleted": False,
                "user_type":  UserRole.CLIENT,
            }

            if status:
                if status not in ("active", "inactive"):
                    raise ValidationException("Status must be 'active' or 'inactive'")
                query["status"] = status

            if search:
                regex = {"$regex": re.escape(search), "$options": "i"}
                query["$or"] = [
                    {"fname": regex},
                    {"lname": regex},
                    {"email": regex},
                ]

            total = await User.find(query).count()
            users = await User.find(query) \
                .sort("-created_at") \
                .skip(skip) \
                .limit(limit) \
                .to_list()

            return {
                "success": True,
                "message": "Clients fetched successfully",
                "total":   total,
                "data": [
                    ClientDataResponse.model_validate(u, from_attributes=True)
                    for u in users
                ],
            }

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to fetch clients")
            raise AppException("Failed to fetch clients", status_code=500)

    @staticmethod
    async def update_client_status(
        client_id: str,
        status:    str,
        admin_id:  str,
    ) -> dict:
        """
        Returns MessageResponse-shaped dict.
        Router returns this directly.
        """
        try:
            user = await UserService._get_active_client(client_id)
            user.status     = status
            user.updated_by = admin_id
            await user.save()

            action = "activated" if status == "active" else "suspended"
            return {
                "success": True,
                "message": f"Client {action} successfully",
            }

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to update client status client_id=%s", client_id
            )
            raise AppException("Failed to update client status", status_code=500)

    @staticmethod
    async def delete_client(client_id: str, admin_id: str) -> dict:
        """
        Returns MessageResponse-shaped dict.
        Router returns this directly.
        """
        try:
            user = await UserService._get_active_client(client_id)
            await user.soft_delete(admin_id)

            return {
                "success": True,
                "message": "Client deleted successfully",
            }

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to delete client client_id=%s", client_id)
            raise AppException("Failed to delete client", status_code=500)

    # ─────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────

    @staticmethod
    async def _get_active_client(user_id: str) -> User:
        if not ObjectId.is_valid(user_id):
            raise ValidationException("Invalid client ID")

        user = await User.get(user_id)

        if not user or user.is_deleted:
            raise NotFoundException("Client not found")

        # Guard — prevent admin accidentally passing a provider ID
        if user.user_type != UserRole.CLIENT:
            raise ValidationException("User is not a client")

        return user


# ─────────────────────────────────────────
# Module-level helper
# ─────────────────────────────────────────

def _build_client_data(user: User) -> ClientDataResponse:
    """Convert User document → ClientDataResponse schema."""
    return ClientDataResponse.model_validate(user, from_attributes=True)