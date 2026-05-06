import re
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import BackgroundTasks, UploadFile
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import (
    AppException,
    ConflictException,
    NotFoundException,
    ValidationException,
)
from app.core.security import hash_password
from app.models.user import User, UserRole, UserStatus
from app.schemas.provider import ProviderApprovalAction, ProviderStatusFilter
from app.utils.email import send_mail
from app.utils.file_upload import (
    delete_file,
    save_provider_portfolio_image,
    save_provider_profile_image,
)
from app.utils.logger import app_logger
from app.services.notification_orchestrator import NotificationOrchestrator
from app.models.service import Service, ServiceApprovalStatus


PORTFOLIO_MAX_FALLBACK = 4


class ProviderService:

    # ─────────────────────────────────────────
    # Registration
    # ─────────────────────────────────────────

    @staticmethod
    async def register_provider(
        email:            str,
        password:         str,
        business_name:    str,
        background_tasks: BackgroundTasks,
        fname:            Optional[str]        = None,
        lname:            Optional[str]        = None,
        phone:            Optional[str]        = None,
        bio:              Optional[str]        = None,
        services:         Optional[str]        = None,  # kept for backward compat, ignored
        profile_image:    Optional[UploadFile] = None,
        portfolio_image:  Optional[UploadFile] = None,
    ) -> dict:
        """
        Returns MessageResponse-shaped dict.
        Router returns this directly.
        """
        email = email.strip().lower()

        # ✅ FIXED QUERY + LOGIC
        existing_user = await User.find_one({"email": email})

        if existing_user:
            # ❌ Block if active + approved
            if not existing_user.is_deleted and existing_user.is_provider_approved:
                raise ConflictException("Email already registered")

            # ❌ Block if pending approval
            if not existing_user.is_deleted and not existing_user.is_provider_approved:
                raise ConflictException("Provider already registered and pending approval")

            # ✔ Reuse rejected OR deleted user
            provider = existing_user
        else:
            provider = User(email=email)

        profile_url      = await save_provider_profile_image(profile_image) if profile_image else None
        portfolio_images = (
            [await save_provider_portfolio_image(portfolio_image)]
            if portfolio_image else []
        )
        full_name = f"{fname or ''} {lname or ''}".strip() or None

        try:
            provider.password = hash_password(password)
            provider.fname = fname
            provider.lname = lname
            provider.full_name = full_name
            provider.phone = phone
            provider.user_type = UserRole.PROVIDER
            provider.email_verified = False
            provider.status = UserStatus.ACTIVE
            provider.is_provider_approved = False
            provider.business_name = business_name
            provider.description = bio
            provider.profile_image = profile_url
            provider.portfolio_images = portfolio_images
            provider.is_deleted = False  # important for reactivation
        except PydanticValidationError as e:
            first = e.errors()[0]
            field = " -> ".join(str(loc) for loc in first.get("loc", []))
            msg   = first.get("msg", "Invalid value")
            raise ValidationException(f"{field}: {msg}" if field else msg)

        # ✅ SAVE LOGIC (UPDATED)
        if existing_user:
            await provider.save()
        else:
            await provider.insert()

        # Assign free provider plan — never blocks registration on failure
        try:
            from app.services.subscription_service import SubscriptionService
            await SubscriptionService.assign_free_plan(
                user_id=str(provider.id),
                user_type=provider.user_type,
            )
        except Exception as e:
            app_logger.error(
                "Failed to assign free plan on provider registration user_id=%s: %s",
                str(provider.id), e,
            )

        # Notify all admins — never blocks registration on failure
        try:
            admins = await User.find(
                User.user_type  == UserRole.ADMIN,
                User.is_deleted == False,
            ).to_list()

            for admin in admins:
                background_tasks.add_task(
                    NotificationOrchestrator.notify_user,
                    user_id=str(admin.id),
                    title="New Provider Registration",
                    body=f"{business_name} is waiting for approval.",
                    notification_type="PROVIDER_PENDING",
                    background_tasks=background_tasks,
                    data={"provider_id": str(provider.id)},
                    path="/admin/providers?status=pending",
                    send_in_app=True,
                    send_push=True,
                )
        except Exception as exc:
            app_logger.error("Admin notification failed: %s", exc)

        # Registration email — never blocks registration on failure
        try:
            await send_mail(
                {"to": provider.email, "subject": "Provider account under review"},
                {
                    "fname":                 business_name,
                    "email":                 provider.email,
                    "providerRegisteration": True,
                },
                "email-template.html",
            )
        except Exception as exc:
            app_logger.error("Provider registration email failed: %s", exc)

        return {
            "success": True,
            "message": "Provider registration submitted for approval",
        }
    # ─────────────────────────────────────────
    # Read — list
    # ─────────────────────────────────────────

    @staticmethod
    async def get_providers(
        page:          int,
        limit:         int,
        service:       Optional[str]  = None,
        status_filter: Optional[str]  = None,
        search:        Optional[str]  = None,
        current_user:  Optional[User] = None,
        is_admin:      bool           = False,
    ) -> dict:
        """
        Returns PaginatedResponse-shaped dict: success, message, total, data.
        data contains raw User documents — router validates them into the
        appropriate response schema (PublicProviderResponse or AdminProviderResponse).
        """
        try:
            skip = (page - 1) * limit
            query: Dict[str, Any] = {"user_type": UserRole.PROVIDER}

            # Role-based base filter
            if is_admin:
                query["is_deleted"] = False
                # Use enum values explicitly — avoids raw string comparison bugs
                if status_filter == ProviderStatusFilter.PENDING.value:
                    query["is_provider_approved"]      = False
                    query["provider_rejection_reason"] = None
                elif status_filter == ProviderStatusFilter.APPROVED.value:
                    query["is_provider_approved"] = True
                elif status_filter == ProviderStatusFilter.REJECTED.value:
                    query["is_provider_approved"]      = False
                    query["provider_rejection_reason"] = {"$ne": None}
            else:
                query.update({
                    "is_provider_approved": True,
                    "status":               UserStatus.ACTIVE,
                    "is_deleted":           False,
                })

            # Service filter
            if service:
                matching_services = await Service.find({
                    "title":           {"$regex": re.escape(service), "$options": "i"},
                    "approval_status": ServiceApprovalStatus.APPROVED,
                    "is_active":       True,
                    "is_deleted":      False,
                }).project({"provider_id": 1}).to_list()

                matching_provider_ids = list({s.provider_id for s in matching_services})
                if not matching_provider_ids:
                    # Early return — no providers match, skip DB query
                    return {
                        "success": True,
                        "message": "Providers fetched successfully",
                        "total":   0,
                        "data":    [],
                    }
                query["_id"] = {"$in": [ObjectId(pid) for pid in matching_provider_ids]}

            # Search filter
            if search:
                pattern = {"$regex": re.escape(search), "$options": "i"}
                query["$or"] = [
                    {"fname":         pattern},
                    {"lname":         pattern},
                    {"business_name": pattern},
                ]

            total     = await User.find(query).count()
            providers = (
                await User.find(query)
                .sort("-created_at")
                .skip(skip)
                .limit(limit)
                .to_list()
            )

            # Fetch services for the current page of providers via aggregation
            services_by_provider: Dict[str, List[str]] = {}
            if providers:
                provider_ids    = [str(p.id) for p in providers]
                service_query   = {
                    "provider_id": {"$in": provider_ids},
                    "is_deleted":  False,
                }
                if not is_admin:
                    service_query.update({
                        "approval_status": ServiceApprovalStatus.APPROVED,
                        "is_active":       True,
                    })
                async for doc in Service.get_pymongo_collection().aggregate([
                    {"$match": service_query},
                    {"$group": {"_id": "$provider_id", "services": {"$push": "$title"}}},
                ]):
                    services_by_provider[doc["_id"]] = doc["services"]

            # Attach aggregated services back onto each provider document.
            # We set a transient attribute so model_validate(from_attributes=True)
            # in the router can read it from the object without extra mapping.
            for provider in providers:
                provider_id_str          = str(provider.id)
                provider._services_cache = services_by_provider.get(provider_id_str, [])

            return {
                "success": True,
                "message": "Providers fetched successfully",
                "total":   total,
                "data":    providers,  # raw User documents — router validates into schema
            }

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to fetch providers")
            raise AppException("Failed to fetch providers", status_code=500)

    # ─────────────────────────────────────────
    # Read — public single detail
    # ─────────────────────────────────────────

    @staticmethod
    async def get_provider_detail(
        provider_id:  str,
        current_user: Optional[User] = None,
    ) -> User:
        """
        Returns the User document.
        Router validates into PublicProviderResponse.
        Paid-client extra fields (phone, email) are attached as transient
        attributes so model_validate picks them up via from_attributes=True.
        """
        if not ObjectId.is_valid(provider_id):
            raise ValidationException("Invalid provider ID")

        provider = await User.get(provider_id)
        if not provider or provider.user_type != UserRole.PROVIDER:
            raise NotFoundException("Provider not found")
        if provider.is_deleted or not provider.is_provider_approved:
            raise NotFoundException("Provider not found")

        # Fetch approved services for this provider
        service_query = {
            "provider_id":     str(provider.id),
            "is_deleted":      False,
            "approval_status": ServiceApprovalStatus.APPROVED,
            "is_active":       True,
        }
        provider._services_cache = [
            doc.title async for doc in Service.find(service_query)
        ]

        # Mask contact details unless the user has a paid plan
        provider._expose_contact = False
        if current_user and current_user.user_type == UserRole.CLIENT:
            try:
                from app.services.subscription_service import SubscriptionService
                features = await SubscriptionService.get_user_features(
                    str(current_user.id), current_user.user_type
                )
                provider._expose_contact = getattr(features, "can_view_full_profiles", False)
            except Exception:
                app_logger.warning(
                    "Could not fetch subscription features for user_id=%s",
                    str(current_user.id),
                )

        return provider

    # ─────────────────────────────────────────
    # Read — single (admin / own profile)
    # ─────────────────────────────────────────

    @staticmethod
    async def get_provider(provider_id: str, is_admin: bool = False) -> User:
        """Returns the raw User document — router validates into AdminProviderResponse."""
        if not ObjectId.is_valid(provider_id):
            raise ValidationException("Invalid provider ID")

        provider = await User.get(provider_id)

        if not provider or provider.user_type != UserRole.PROVIDER:
            raise NotFoundException("Provider not found")

        if not is_admin:
            if provider.is_deleted or not provider.is_provider_approved:
                raise NotFoundException("Provider not found")

        return provider

    # ─────────────────────────────────────────
    # Update profile
    # ─────────────────────────────────────────

    @staticmethod
    async def update_provider_profile(
        provider_id:     str,
        business_name:   Optional[str]        = None,
        description:     Optional[str]        = None,
        phone:           Optional[str]        = None,
        services:        Optional[str]        = None,  # ignored — managed via service endpoints
        website_url:     Optional[str]        = None,
        social_links:    Optional[dict]       = None,
        profile_image:   Optional[UploadFile] = None,
        portfolio_image: Optional[UploadFile] = None,
    ) -> dict:
        """Returns MessageResponse-shaped dict. Router returns this directly."""
        try:
            provider = await ProviderService._get_provider_or_404(provider_id)

            if business_name is not None:
                provider.business_name = business_name.strip()
            if description is not None:
                provider.description = description.strip()
            if phone is not None:
                provider.phone = phone.strip()
            if website_url is not None:
                provider.website_url = website_url.strip()
            if social_links is not None:
                provider.social_links = social_links

            if profile_image:
                if provider.profile_image:
                    ProviderService._safe_delete(provider.profile_image)
                provider.profile_image = await save_provider_profile_image(profile_image)

            if portfolio_image:
                max_images = PORTFOLIO_MAX_FALLBACK
                try:
                    from app.services.subscription_service import SubscriptionService
                    features   = await SubscriptionService.get_user_features(
                        provider_id, UserRole.PROVIDER
                    )
                    max_images = features.max_portfolio_images
                except Exception:
                    app_logger.warning(
                        "Could not fetch subscription features for provider_id=%s, "
                        "using fallback max=%d",
                        provider_id, PORTFOLIO_MAX_FALLBACK,
                    )

                if max_images != -1 and len(provider.portfolio_images) >= max_images:
                    oldest = provider.portfolio_images.pop(0)
                    ProviderService._safe_delete(oldest)

                provider.portfolio_images.append(
                    await save_provider_portfolio_image(portfolio_image)
                )

            provider.updated_by = provider_id
            await provider.save()

            return {"success": True, "message": "Profile updated successfully"}

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to update provider profile provider_id=%s", provider_id
            )
            raise AppException("Failed to update profile", status_code=500)

    # ─────────────────────────────────────────
    # Approval
    # ─────────────────────────────────────────

    @staticmethod
    async def update_approval(
        provider_id:      str,
        action:           ProviderApprovalAction,
        reason:           Optional[str],
        admin_id:         str,
        background_tasks: BackgroundTasks,
    ) -> dict:
        """Returns MessageResponse-shaped dict. Router returns this directly."""
        try:
            provider    = await ProviderService._get_provider_or_404(provider_id)
            is_approved = action == ProviderApprovalAction.APPROVE

            if is_approved and provider.is_provider_approved:
                return {"success": True, "message": "Provider is already approved"}

            provider.is_provider_approved      = is_approved
            provider.provider_rejection_reason = None if is_approved else reason
            provider.updated_by                = admin_id
            await provider.save()

            background_tasks.add_task(
                ProviderService._send_approval_email,
                provider.email,
                provider.business_name or "Provider",
                is_approved,
                reason,
            )

            await NotificationOrchestrator.notify_user(
                user_id=str(provider.id),
                title="Provider Application Update",
                body=(
                    "Your provider application has been approved. "
                    "You can now list your services."
                    if is_approved
                    else "Your provider application has been rejected"
                    + (f": {reason}" if reason else ".")
                ),
                notification_type=(
                    "PROVIDER_APPROVAL" if is_approved else "PROVIDER_REJECTION"
                ),
                background_tasks=background_tasks,
                data={
                    "provider_id": provider_id,
                    "approved":    str(is_approved),
                },
                path="/provider/profile",
                send_in_app=True,
                send_push=True,
            )

            verb = "approved" if is_approved else "rejected"
            return {"success": True, "message": f"Provider {verb} successfully"}

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to update provider approval provider_id=%s", provider_id
            )
            raise AppException("Failed to update provider approval", status_code=500)

    # ─────────────────────────────────────────
    # Delete
    # ─────────────────────────────────────────

    @staticmethod
    async def delete_provider(
        provider_id:      str,
        admin_id:         str,
        background_tasks: BackgroundTasks,
    ) -> dict:
        """Returns MessageResponse-shaped dict. Router returns this directly."""
        try:
            provider = await ProviderService._get_provider_or_404(provider_id)

            if provider.is_deleted:
                return {"success": True, "message": "Provider is already deleted"}

            await provider.soft_delete(admin_id)

            await NotificationOrchestrator.notify_user(
                user_id=str(provider.id),
                title="Account Deleted",
                body="Your provider account has been deleted by an administrator.",
                notification_type="ACCOUNT_DELETED",
                background_tasks=background_tasks,
                data={"provider_id": provider_id},
                path="/",
                send_in_app=True,
                send_push=True,
            )

            return {"success": True, "message": "Provider deleted successfully"}

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to delete provider provider_id=%s", provider_id)
            raise AppException("Failed to delete provider", status_code=500)

    # ─────────────────────────────────────────
    # Restore
    # ─────────────────────────────────────────

    @staticmethod
    async def restore_provider(
        provider_id:      str,
        admin_id:         str,
        background_tasks: BackgroundTasks,
    ) -> dict:
        """Returns MessageResponse-shaped dict. Router returns this directly."""
        try:
            provider = await ProviderService._get_provider_or_404(
                provider_id, allow_deleted=True
            )

            if not provider.is_deleted:
                return {"success": True, "message": "Provider is not deleted"}

            provider.is_deleted  = False
            provider.deleted_at  = None
            provider.deleted_by  = None
            provider.updated_by  = admin_id
            await provider.save()

            await NotificationOrchestrator.notify_user(
                user_id=str(provider.id),
                title="Account Restored",
                body="Your provider account has been restored by an administrator.",
                notification_type="ACCOUNT_RESTORED",
                background_tasks=background_tasks,
                data={"provider_id": provider_id},
                path="/provider/dashboard",
                send_in_app=True,
                send_push=True,
            )

            return {"success": True, "message": "Provider restored successfully"}

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to restore provider provider_id=%s", provider_id
            )
            raise AppException("Failed to restore provider", status_code=500)

    # ─────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────

    @staticmethod
    async def _get_provider_or_404(
        provider_id:   str,
        allow_deleted: bool = False,
    ) -> User:
        if not ObjectId.is_valid(provider_id):
            raise ValidationException("Invalid provider ID")

        provider = await User.get(provider_id)

        if not provider or provider.user_type != UserRole.PROVIDER:
            raise NotFoundException("Provider not found")

        if provider.is_deleted and not allow_deleted:
            raise NotFoundException("Provider not found")

        return provider

    @staticmethod
    def _safe_delete(path: str) -> None:
        try:
            delete_file(path)
        except Exception as exc:
            app_logger.error("Failed to delete file %s: %s", path, exc)

    @staticmethod
    async def _send_approval_email(
        email:       str,
        name:        str,
        is_approved: bool,
        reason:      Optional[str] = None,
    ) -> None:
        try:
            await send_mail(
                {
                    "to":      email,
                    "subject": (
                        "Your provider account is approved"
                        if is_approved
                        else "Your provider account was rejected"
                    ),
                },
                {
                    "fname":            name,
                    "email":            email,
                    "reason":           reason,
                    "providerApproved": is_approved,
                    "providerRejected": not is_approved,
                },
                "email-template.html",
            )
        except Exception as exc:
            app_logger.error("Provider approval email failed: %s", exc)