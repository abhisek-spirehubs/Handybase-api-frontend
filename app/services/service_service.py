import re
from bson import ObjectId
from fastapi import UploadFile, BackgroundTasks
from typing import Optional

from app.models.service import Service, ServiceApprovalStatus
from app.models.user import User, UserRole
from app.schemas.common import StatusEnum
from app.schemas.service import ServiceApprovalAction
from app.schemas.notification import NotificationCreate
from app.services.notification_service import NotificationService
from app.utils.file_upload import save_file, delete_file
from app.utils.email import send_mail
from app.utils.logger import app_logger
from app.core.exceptions import (
    NotFoundException,
    ForbiddenException,
    ValidationException,
    AppException,
)


class ServiceService:

    # ─────────────────────────────────────────
    # Provider — create
    # ─────────────────────────────────────────

    @staticmethod
    async def create_service(
        provider_id: str,
        title: str,
        description: Optional[str],
        category_id: str,
        price: float,
        duration: int,
        city: Optional[str],
        state: Optional[str],
        image: Optional[UploadFile],
    ) -> Service:
        try:
            # ── Validate category_id ───────────────────────────────
            if not category_id or not category_id.strip():
                raise ValidationException("Category id is required")

            if not ObjectId.is_valid(category_id):
                raise ValidationException("Invalid category id")
            # ──────────────────────────────────────────────────────

            user = await User.get(provider_id)
            if not user or user.is_deleted:
                raise NotFoundException("User not found")

            if user.user_type not in [UserRole.ADMIN, UserRole.PROVIDER]:
                raise ForbiddenException("Only providers can create services")

            if user.user_type == UserRole.PROVIDER and not user.is_provider_approved:
                raise ForbiddenException("Your provider account is not approved yet")

            # ── Subscription gate ─────────────────────────────────────────
            if user.user_type == UserRole.PROVIDER:
                from app.services.subscription_service import SubscriptionService

                features = await SubscriptionService.get_user_features(
                    provider_id, UserRole.PROVIDER
                )

                if not features.can_list_services:
                    raise ForbiddenException(
                        "Service listings require Tier 2 or above. "
                        "Please upgrade your plan."
                    )

                if features.max_services != -1:
                    existing_count = await Service.find(
                        Service.provider_id == provider_id,
                        Service.is_deleted == False,
                    ).count()

                    if existing_count >= features.max_services:
                        raise ForbiddenException(
                            f"You have reached the maximum of {features.max_services} "
                            f"services on your current plan. Upgrade to add more."
                        )
            # ─────────────────────────────────────────────────────────────

            image_urls = []
            if image:
                url = await save_file(image, "services")
                image_urls.append(url)

            is_admin = user.user_type == UserRole.ADMIN

            service = Service(
                provider_id=str(user.id),
                category_id=category_id,
                title=title,
                description=description,
                price=price,
                duration=duration,
                city=city,
                state=state,
                images=image_urls,
                approval_status=(
                    ServiceApprovalStatus.APPROVED
                    if is_admin
                    else ServiceApprovalStatus.PENDING
                ),
                is_active=is_admin,
                status=StatusEnum.ACTIVE,
                created_by=str(user.id),
            )

            await service.insert()

            # ── Notify all admins — new service pending approval ──────────
            if user.user_type == UserRole.PROVIDER:
                try:
                    admins = await User.find(
                        User.user_type == UserRole.ADMIN,
                        User.is_deleted == False,
                    ).to_list()

                    for admin in admins:
                        await NotificationService.create_notification(
                            NotificationCreate(
                                user_id=str(admin.id),
                                title="New Service Submitted",
                                note=f'"{title}" submitted by '
                                    f'{user.business_name or user.fname or "a provider"} '
                                    f"is awaiting approval.",
                                type="SERVICE_PENDING",
                                is_admin=True,
                                fcm_token=admin.fcm_token,
                                data={
                                    "service_id":   str(service.id),
                                    "provider_id":  provider_id,
                                    "service_title": title,
                                    "type":         "SERVICE_PENDING",
                                },
                            )
                        )
                except Exception as e:
                    app_logger.error(
                        "Admin notification failed for new service service_id=%s: %s",
                        str(service.id), e,
                    )
            # ─────────────────────────────────────────────────────────────

            return service

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to create service provider_id=%s", provider_id)
            raise AppException("Failed to create service", status_code=500)
    # ─────────────────────────────────────────
    # Read — single
    # ─────────────────────────────────────────

    @staticmethod
    async def get_by_id(service_id: str) -> Service:
        try:
            if not ObjectId.is_valid(service_id):
                raise ValidationException("Invalid service id")

            service = await Service.get(service_id)
            if not service or service.is_deleted:
                raise NotFoundException("Service not found")

            return service

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to fetch service id=%s", service_id)
            raise AppException("Failed to fetch service", status_code=500)

    # ─────────────────────────────────────────
    # Update
    # ─────────────────────────────────────────

    @staticmethod
    async def update_service(
        service_id: str,
        user: User,
        title: str,
        description: Optional[str],
        category_id: str,
        price: float,
        duration: int,
        city: Optional[str],
        state: Optional[str],
        image: Optional[UploadFile],
    ) -> Service:
        try:
            if not ObjectId.is_valid(service_id):
                raise ValidationException("Invalid service id")

            service = await Service.get(service_id)
            if not service or service.is_deleted:
                raise NotFoundException("Service not found")

            if user.user_type != UserRole.ADMIN and service.provider_id != str(user.id):
                raise ForbiddenException("Not allowed")

            service.title       = title
            service.description = description
            service.category_id = category_id
            service.price       = price
            service.duration    = duration
            service.city        = city
            service.state       = state
            service.updated_by  = str(user.id)

            if image:
                if service.images:
                    delete_file(service.images[0])
                url = await save_file(image, "services")
                service.images = [url]

            # Provider edit re-submits for admin approval
            if user.user_type == UserRole.PROVIDER:
                service.approval_status = ServiceApprovalStatus.PENDING
                service.is_active       = False
                service.rejection_reason = None

                # ── Notify admins — service re-submitted after edit ───────
                try:
                    admins = await User.find(
                        User.user_type == UserRole.ADMIN,
                        User.is_deleted == False,
                    ).to_list()

                    for admin in admins:
                        await NotificationService.create_notification(
                            NotificationCreate(
                                user_id=str(admin.id),
                                title="Service Updated — Needs Review",
                                note=f'"{title}" has been updated by '
                                     f'{user.business_name or user.fname or "a provider"} '
                                     f"and is awaiting re-approval.",
                                type="SERVICE_RESUBMITTED",
                                is_admin=True,
                                fcm_token=admin.fcm_token,
                                data={
                                    "service_id":    service_id,
                                    "provider_id":   str(user.id),
                                    "service_title": title,
                                    "type":          "SERVICE_RESUBMITTED",
                                },
                            )
                        )
                except Exception as e:
                    app_logger.error(
                        "Admin notification failed for service update service_id=%s: %s",
                        service_id, e,
                    )
                # ─────────────────────────────────────────────────────────

            await service.save()
            return service

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to update service id=%s", service_id)
            raise AppException("Failed to update service", status_code=500)

    # ─────────────────────────────────────────
    # Delete
    # ─────────────────────────────────────────

    @staticmethod
    async def delete_service(service_id: str, user: User) -> None:
        try:
            if not ObjectId.is_valid(service_id):
                raise ValidationException("Invalid service id")

            service = await Service.get(service_id)
            if not service or service.is_deleted:
                raise NotFoundException("Service not found")

            if user.user_type != UserRole.ADMIN and service.provider_id != str(user.id):
                raise ForbiddenException("Not allowed")

            await service.soft_delete(str(user.id))

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to delete service id=%s", service_id)
            raise AppException("Failed to delete service", status_code=500)

    # ─────────────────────────────────────────
    # Read — role-aware list + search
    # ─────────────────────────────────────────

# app/services/service_service.py

    @staticmethod
    async def get_services(
        current_user: Optional[User],
        page: int,
        limit: int,
        approval_status: Optional[str] = None,
        provider_id: Optional[str] = None,
        category_id: Optional[str] = None,
        search: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        sort_by: str = "newest",
    ) -> dict:
        try:
            skip = (page - 1) * limit
            query: dict = {"is_deleted": False}

            role = current_user.user_type if current_user else None

            if role == UserRole.ADMIN:
                if provider_id:
                    if not ObjectId.is_valid(provider_id):
                        raise ValidationException("Invalid provider id")
                    query["provider_id"] = provider_id
                if approval_status:
                    query["approval_status"] = approval_status.upper()

            elif role == UserRole.PROVIDER:
                query["provider_id"] = str(current_user.id)
                if approval_status:
                    query["approval_status"] = approval_status.upper()

            else:
                query["approval_status"] = ServiceApprovalStatus.APPROVED
                query["is_active"]       = True

            if category_id:
                if not ObjectId.is_valid(category_id):
                    raise ValidationException("Invalid category id")
                try:
                    obj_id = ObjectId(category_id)
                    query["category_id"] = {"$in": [category_id, obj_id]}
                except Exception:
                    query["category_id"] = category_id

            if city:
                query["city"] = {"$regex": re.escape(city), "$options": "i"}

            if state:
                query["state"] = {"$regex": re.escape(state), "$options": "i"}

            if min_price is not None or max_price is not None:
                price_filter: dict = {}
                if min_price is not None:
                    price_filter["$gte"] = min_price
                if max_price is not None:
                    price_filter["$lte"] = max_price
                query["price"] = price_filter

            if search:
                query["$text"] = {"$search": search}

            sort_map = {
                "newest":     [("created_at", -1)],
                "oldest":     [("created_at", 1)],
                "price_low":  [("price", 1)],
                "price_high": [("price", -1)],
            }
            sort = sort_map.get(sort_by, sort_map["newest"])

            total = await Service.find(query).count()
            data = await Service.find(query) \
                .sort(sort) \
                .skip(skip) \
                .limit(limit) \
                .to_list()

            return {
                "success": True,
                "message": "Services fetched successfully",
                "total": total,
                "data": data,
            }

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to fetch services")
            raise AppException("Failed to fetch services", status_code=500)
    # ─────────────────────────────────────────
    # Admin — approval
    # ─────────────────────────────────────────

    @staticmethod
    async def update_service_approval(
        service_id: str,
        action: ServiceApprovalAction,
        reason: Optional[str],
        admin_id: str,
        background_tasks: BackgroundTasks,
    ) -> Service:
        try:
            if not ObjectId.is_valid(service_id):
                raise ValidationException("Invalid service id")

            service = await Service.get(service_id)
            if not service or service.is_deleted:
                raise NotFoundException("Service not found")

            is_approving = action == ServiceApprovalAction.APPROVE

            if is_approving and service.approval_status == ServiceApprovalStatus.APPROVED:
                return service

            service.approval_status  = (
                ServiceApprovalStatus.APPROVED
                if is_approving
                else ServiceApprovalStatus.REJECTED
            )
            service.is_active        = is_approving
            service.rejection_reason = None if is_approving else reason
            service.updated_by       = admin_id
            await service.save()

            provider = await User.get(service.provider_id)

            # ── Email provider in background ──────────────────────────────
            if provider:
                background_tasks.add_task(
                    send_mail,
                    {
                        "to": provider.email,
                        "subject": (
                            "Your service was approved"
                            if is_approving
                            else "Your service was rejected"
                        ),
                    },
                    replacements={
                        "fname":           provider.fname or "Provider",
                        "email":           provider.email,
                        "serviceTitle":    service.title,
                        "reason":          reason,
                        "serviceApproved": is_approving,
                        "serviceRejected": not is_approving,
                    },
                    html_file_name="email-template.html",
                )

            # ── In-app + push notification to provider ────────────────────
            if provider:
                try:
                    await NotificationService.create_notification(
                        NotificationCreate(
                            user_id=str(provider.id),
                            title=(
                                "Service Approved"
                                if is_approving
                                else "Service Rejected"
                            ),
                            note=(
                                f'Your service "{service.title}" has been approved '
                                f"and is now live."
                                if is_approving
                                else f'Your service "{service.title}" has been rejected'
                                + (f": {reason}" if reason else ".")
                            ),
                            type=(
                                "SERVICE_APPROVED"
                                if is_approving
                                else "SERVICE_REJECTED"
                            ),
                            fcm_token=provider.fcm_token,
                            data={
                                "service_id":    service_id,
                                "service_title": service.title,
                                "approved":      str(is_approving),
                                "reason":        reason or "",
                                "type": (
                                    "SERVICE_APPROVED"
                                    if is_approving
                                    else "SERVICE_REJECTED"
                                ),
                            },
                        )
                    )
                except Exception as e:
                    app_logger.error(
                        "Provider notification failed for service approval "
                        "service_id=%s: %s",
                        service_id, e,
                    )
            # ─────────────────────────────────────────────────────────────

            return service

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to update service approval id=%s", service_id
            )
            raise AppException("Failed to update service approval", status_code=500)
