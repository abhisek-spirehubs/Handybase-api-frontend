from datetime import datetime, timedelta
from typing import Optional, Union

from app.models.plan import (
    PlanType, PlanFeatures,
    CLIENT_FREE_FEATURES,
    PROVIDER_TIER1_FEATURES,
)
from app.models.client_plan import ClientPlan
from app.models.provider_plan import ProviderPlan
from app.models.client_subscription import ClientSubscription
from app.models.provider_subscription import ProviderSubscription
from app.models.subscription import SubscriptionStatus
from app.models.user import User, UserRole
from app.utils.logger import app_logger
from app.core.exceptions import (
    NotFoundException,
    ValidationException,
    AppException,
)
from app.core.config import settings
from app.utils.email import send_mail
from fastapi import BackgroundTasks
from app.services.notification_orchestrator import NotificationOrchestrator
from bson import ObjectId


def _utc_now() -> datetime:
    return datetime.utcnow()


_SUBJECT_NEW     = "Subscription Confirmed — Handybase"
_SUBJECT_UPGRADE = "Plan Upgraded — Handybase"
_SUBJECT_RENEW   = "Subscription Renewed — Handybase"
_SUBJECT_CANCEL  = "Subscription Cancelled — Handybase"

_UPGRADE_ORDER = {
    PlanType.CLIENT_FREE.value:    0,
    PlanType.CLIENT_PAID.value:    1,
    PlanType.PROVIDER_TIER1.value: 0,
    PlanType.PROVIDER_TIER2.value: 1,
    PlanType.PROVIDER_TIER3.value: 2,
}

_CLIENT_PLAN_TYPES   = {"client_free", "client_paid"}
_PROVIDER_PLAN_TYPES = {"provider_tier1", "provider_tier2", "provider_tier3"}


def _get_models(user_type: UserRole):
    """Returns (PlanModel, SubscriptionModel) based on user type."""
    if user_type == UserRole.CLIENT:
        return ClientPlan, ClientSubscription
    return ProviderPlan, ProviderSubscription


class SubscriptionService:

    # ─────────────────────────────────────────
    # Internal helper — send push silently
    # ─────────────────────────────────────────

    @staticmethod
    async def _push(
        user: User,
        title: str,
        body: str,
        notification_type: str,
        path: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> None:
        try:
            from app.services.notification_service import NotificationService
            from app.schemas.notification import NotificationCreate

            push_data = {**(data or {})}
            if path:
                push_data["path"] = path

            await NotificationService.create_notification(
                NotificationCreate(
                    user_id=str(user.id),
                    title=title,
                    note=body,
                    type=notification_type,
                    path=path,
                    fcm_token=user.fcm_token,
                    data=push_data,
                )
            )
        except Exception as e:
            app_logger.error(
                "Subscription push failed user_id=%s type=%s: %s",
                str(user.id), notification_type, e,
            )

    # ─────────────────────────────────────────
    # Internal helper — get plan by id
    # ─────────────────────────────────────────

    @staticmethod
    async def _get_plan(plan_id: str, user_type: UserRole):
        """Fetches plan from correct collection based on user_type."""
        PlanModel, _ = _get_models(user_type)
        plan = await PlanModel.get(plan_id)
        if not plan or plan.is_deleted or not plan.is_active:
            raise NotFoundException("Plan not found or no longer available")
        return plan

    # ─────────────────────────────────────────
    # Read
    # ─────────────────────────────────────────

    @staticmethod
    async def get_active_subscription(
        user_id: str,
        user_type: Optional[UserRole] = None,
    ) -> Optional[Union[ClientSubscription, ProviderSubscription]]:
        """
        Returns current active subscription or None.
        If user_type provided — searches correct collection directly.
        If not provided — tries client first then provider.
        Auto-heals users who registered before plans existed.
        """
        # ── Try to find active subscription ──────────────────────────
        if user_type == UserRole.CLIENT:
            sub = await ClientSubscription.find_one(
                ClientSubscription.user_id == user_id,
                ClientSubscription.status == SubscriptionStatus.ACTIVE,
                ClientSubscription.is_deleted == False,
            )
        elif user_type == UserRole.PROVIDER:
            sub = await ProviderSubscription.find_one(
                ProviderSubscription.user_id == user_id,
                ProviderSubscription.status == SubscriptionStatus.ACTIVE,
                ProviderSubscription.is_deleted == False,
            )
        else:
            # No user_type hint — try both
            sub = await ClientSubscription.find_one(
                ClientSubscription.user_id == user_id,
                ClientSubscription.status == SubscriptionStatus.ACTIVE,
                ClientSubscription.is_deleted == False,
            )
            if not sub:
                sub = await ProviderSubscription.find_one(
                    ProviderSubscription.user_id == user_id,
                    ProviderSubscription.status == SubscriptionStatus.ACTIVE,
                    ProviderSubscription.is_deleted == False,
                )

        if sub:
            return sub

        # ── Auto-heal ────────────────────────────────────────────────
        user = await User.get(user_id)
        if user and user.subscription_plan:
            try:
                resolved_type = user_type or user.user_type
                PlanModel, SubModel = _get_models(resolved_type)

                plan = await PlanModel.find_one(
                    {"plan_type": user.subscription_plan},
                    PlanModel.is_active == True,
                    PlanModel.is_deleted == False,
                )
                if plan:
                    healed_sub = SubModel(
                        user_id=user_id,
                        plan_id=str(plan.id),
                        plan_type=plan.plan_type,
                        status=SubscriptionStatus.ACTIVE,
                        started_at=user.created_at or _utc_now(),
                        expires_at=None,
                        payment_id=f"free_{user_id}",
                        amount_paid=0.0,
                        currency=plan.currency,
                        features_snapshot=plan.features,
                        created_by=user_id,
                    )
                    await healed_sub.insert()
                    app_logger.info(
                        "Auto-healed missing subscription user_id=%s plan=%s",
                        user_id, user.subscription_plan,
                    )
                    return healed_sub
            except Exception as e:
                app_logger.error(
                    "Auto-heal subscription failed user_id=%s: %s", user_id, e
                )

        return None

    @staticmethod
    async def get_user_features(user_id: str, user_type: UserRole) -> PlanFeatures:
        sub = await SubscriptionService.get_active_subscription(user_id, user_type)

        if sub:
            if sub.expires_at and sub.expires_at < _utc_now():
                return (
                    CLIENT_FREE_FEATURES if user_type == UserRole.CLIENT
                    else PROVIDER_TIER1_FEATURES
                )
            return sub.features_snapshot

        if user_type == UserRole.CLIENT:
            return CLIENT_FREE_FEATURES
        elif user_type == UserRole.PROVIDER:
            return PROVIDER_TIER1_FEATURES
        else:
            return PlanFeatures()

    @staticmethod
    async def get_subscription_history(
        user_id: str,
        user_type: Optional[UserRole] = None,
    ) -> list:
        """Returns all subscriptions for user — newest first."""
        if user_type == UserRole.CLIENT:
            return await ClientSubscription.find(
                ClientSubscription.user_id == user_id,
                ClientSubscription.is_deleted == False,
            ).sort("-created_at").to_list()

        if user_type == UserRole.PROVIDER:
            return await ProviderSubscription.find(
                ProviderSubscription.user_id == user_id,
                ProviderSubscription.is_deleted == False,
            ).sort("-created_at").to_list()

        # No hint — combine both
        client_subs = await ClientSubscription.find(
            ClientSubscription.user_id == user_id,
            ClientSubscription.is_deleted == False,
        ).to_list()

        provider_subs = await ProviderSubscription.find(
            ProviderSubscription.user_id == user_id,
            ProviderSubscription.is_deleted == False,
        ).to_list()

        combined = client_subs + provider_subs
        combined.sort(key=lambda x: x.created_at, reverse=True)
        return combined

    @staticmethod
    async def get_all_subscriptions(
        status: Optional[str] = None,
        plan_type: Optional[str] = None,
    ) -> list:
        """Admin — list all subscriptions across both collections."""
        try:
            # Build query for client subscriptions
            client_query = ClientSubscription.find(
                ClientSubscription.is_deleted == False
            )
            if status:
                client_query = client_query.find({"status": status})
            if plan_type:
                client_query = client_query.find({"plan_type": plan_type})
            client_subs = await client_query.to_list()

            # Build query for provider subscriptions
            provider_query = ProviderSubscription.find(
                ProviderSubscription.is_deleted == False
            )
            if status:
                provider_query = provider_query.find({"status": status})
            if plan_type:
                provider_query = provider_query.find({"plan_type": plan_type})
            provider_subs = await provider_query.to_list()

            combined = client_subs + provider_subs
            combined.sort(key=lambda x: x.created_at, reverse=True)
            return combined

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to fetch all subscriptions")
            raise AppException("Failed to fetch subscriptions", status_code=500)

    # ─────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────

    @staticmethod
    def _fname(user: User) -> str:
        return user.fname or user.full_name or "User"

    @staticmethod
    async def _send_cancellation_email(
        user: User,
        plan_name: str,
        cancelled_at: datetime,
        reason: Optional[str],
    ) -> None:
        try:
            from app.utils.email import send_mail
            await send_mail(
                {"to": user.email, "subject": _SUBJECT_CANCEL},
                {
                    "fname":                 SubscriptionService._fname(user),
                    "email":                 user.email,
                    "subscriptionCancelled": True,
                    "showInvoice":           False,
                    "planName":              plan_name,
                    "cancelledAt":           cancelled_at.strftime("%d %B %Y"),
                    "reason":                reason or "Not specified",
                },
                "email-template.html",
            )
            app_logger.info(
                "Cancellation email sent to=%s plan=%s", user.email, plan_name
            )
        except Exception as e:
            app_logger.error(
                "Cancellation email failed user=%s: %s", user.email, e
            )

    # ─────────────────────────────────────────
    # Assign free plan — called on registration
    # ─────────────────────────────────────────

    @staticmethod
    async def assign_free_plan(
        user_id: str,
        user_type: UserRole,
    ) -> Union[ClientSubscription, ProviderSubscription]:
        try:
            PlanModel, SubModel = _get_models(user_type)

            plan_type = (
                PlanType.CLIENT_FREE.value if user_type == UserRole.CLIENT
                else PlanType.PROVIDER_TIER1.value
            )

            plan = await PlanModel.find_one(
                {"plan_type": plan_type},
                PlanModel.is_active == True,
                PlanModel.is_deleted == False,
            )

            if not plan:
                raise NotFoundException(
                    f"Default plan '{plan_type}' not found. "
                    f"Create it via admin API first."
                )

            sub = SubModel(
                user_id=user_id,
                plan_id=str(plan.id),
                plan_type=plan_type,
                status=SubscriptionStatus.ACTIVE,
                started_at=_utc_now(),
                expires_at=None,
                payment_id=f"free_{user_id}",
                amount_paid=0.0,
                currency=plan.currency,
                features_snapshot=plan.features,
                created_by=user_id,
            )
            await sub.insert()

            user = await User.get(user_id)
            if user:
                user.subscription_plan       = plan_type
                user.subscription_expires_at = None
                user.updated_by              = user_id
                await user.save()

            return sub

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to assign free plan user_id=%s", user_id
            )
            raise AppException("Failed to assign plan", status_code=500)

    # ─────────────────────────────────────────
    # Subscribe
    # ─────────────────────────────────────────

    @staticmethod
    async def subscribe(
        user_id: str,
        plan_id: str,
        background_tasks: BackgroundTasks,
        payment_id: Optional[str] = None,
        amount_paid: Optional[float] = None,
        currency: str = "USD",
    ) -> Union[ClientSubscription, ProviderSubscription]:
        try:
            if not ObjectId.is_valid(plan_id):
                raise ValidationException("Invalid plan id")

            user = await User.get(user_id)
            if not user or user.is_deleted:
                raise NotFoundException("User not found")

            PlanModel, SubModel = _get_models(user.user_type)

            plan = await PlanModel.get(plan_id)
            if not plan or plan.is_deleted or not plan.is_active:
                raise NotFoundException("Plan not found or no longer available")

            # Validate plan belongs to correct user type
            if user.user_type == UserRole.CLIENT and plan.plan_type not in _CLIENT_PLAN_TYPES:
                raise ValidationException("This plan is not available for client accounts")
            if user.user_type == UserRole.PROVIDER and plan.plan_type not in _PROVIDER_PLAN_TYPES:
                raise ValidationException("This plan is not available for provider accounts")

            existing = await SubscriptionService.get_active_subscription(
                user_id, user.user_type
            )

            if existing and str(existing.plan_id) == str(plan_id):
                raise ValidationException("You are already subscribed to this plan")

            if existing:
                existing.status              = SubscriptionStatus.CANCELLED
                existing.cancelled_at        = _utc_now()
                existing.cancellation_reason = "Replaced by new subscription"
                existing.updated_by          = user_id
                await existing.save()

            is_free = plan.price == 0.0
            now     = _utc_now()

            sub = SubModel(
                user_id=user_id,
                plan_id=str(plan.id),
                plan_type=plan.plan_type,
                status=SubscriptionStatus.ACTIVE,
                started_at=now,
                expires_at=now + timedelta(days=plan.duration_days) if not is_free else None,
                payment_id=payment_id or f"free_{user_id}",
                amount_paid=amount_paid if amount_paid is not None else plan.price,
                currency=currency,
                features_snapshot=plan.features,
                created_by=user_id,
            )
            await sub.insert()

            user.subscription_plan       = plan.plan_type
            user.subscription_expires_at = sub.expires_at
            user.updated_by              = user_id
            await user.save()

            if not is_free and sub.amount_paid > 0:
                from app.services.invoice_service import InvoiceService
                from app.models.invoice import InvoiceType

                invoice = await InvoiceService.create_invoice(
                    user=user,
                    subscription_id=str(sub.id),
                    plan_id=str(plan.id),
                    plan_name=plan.name,
                    plan_type=plan.plan_type,
                    invoice_type=InvoiceType.NEW_SUBSCRIPTION,
                    subtotal=sub.amount_paid,
                    currency=currency,
                    payment_id=payment_id,
                    period_start=sub.started_at,
                    period_end=sub.expires_at,
                )
                await InvoiceService.send_invoice_email(
                    user=user,
                    invoice=invoice,
                    subject=_SUBJECT_NEW,
                    extra_context={"subscriptionConfirmed": True},
                )

            # Send push via orchestrator
            await NotificationOrchestrator.notify_user(
                user_id=str(user.id),
                title="Subscription Confirmed",
                body=f"You are now subscribed to {plan.name}. Enjoy your new features!",
                notification_type="SUBSCRIPTION_CONFIRMED",
                background_tasks=background_tasks,
                data={
                    "plan_id":   str(plan.id),
                    "plan_name": plan.name,
                    "plan_type": plan.plan_type,
                },
                path="/subscriptions/current",
                send_in_app=True,
                send_push=True,
            )

            return sub

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to subscribe user_id=%s plan_id=%s", user_id, plan_id
            )
            raise AppException("Failed to process subscription", status_code=500)
    # ─────────────────────────────────────────
    # Upgrade
    # ─────────────────────────────────────────

    @staticmethod
    async def upgrade_subscription(
        user_id: str,
        new_plan_id: str,
        background_tasks: BackgroundTasks,
        payment_id: Optional[str] = None,
        amount_paid: Optional[float] = None,
        currency: str = "USD",
    ) -> Union[ClientSubscription, ProviderSubscription]:
        try:
            if not ObjectId.is_valid(new_plan_id):
                raise ValidationException("Invalid plan id")

            user = await User.get(user_id)
            if not user or user.is_deleted:
                raise NotFoundException("User not found")

            PlanModel, SubModel = _get_models(user.user_type)

            new_plan = await PlanModel.get(new_plan_id)
            if not new_plan or new_plan.is_deleted or not new_plan.is_active:
                raise NotFoundException("Plan not found or no longer available")

            existing = await SubscriptionService.get_active_subscription(
                user_id, user.user_type
            )
            if not existing:
                raise ValidationException(
                    "No active subscription found. Use subscribe instead."
                )

            if str(existing.plan_id) == str(new_plan_id):
                raise ValidationException("You are already on this plan")

            current_order = _UPGRADE_ORDER.get(existing.plan_type, 0)
            new_order     = _UPGRADE_ORDER.get(new_plan.plan_type, 0)

            if new_order <= current_order:
                raise ValidationException(
                    "Cannot upgrade to a lower or equal plan. "
                    "Use subscribe to change plans."
                )

            existing.status              = SubscriptionStatus.CANCELLED
            existing.cancelled_at        = _utc_now()
            existing.cancellation_reason = f"Upgraded to {new_plan.name}"
            existing.updated_by          = user_id
            await existing.save()

            now = _utc_now()
            sub = SubModel(
                user_id=user_id,
                plan_id=str(new_plan.id),
                plan_type=new_plan.plan_type,
                status=SubscriptionStatus.ACTIVE,
                started_at=now,
                expires_at=now + timedelta(days=new_plan.duration_days),
                payment_id=payment_id or f"manual_{user_id}",
                amount_paid=amount_paid if amount_paid is not None else new_plan.price,
                currency=currency,
                features_snapshot=new_plan.features,
                created_by=user_id,
            )
            await sub.insert()

            user.subscription_plan       = new_plan.plan_type
            user.subscription_expires_at = sub.expires_at
            user.updated_by              = user_id
            await user.save()

            if amount_paid and amount_paid > 0:
                from app.services.invoice_service import InvoiceService
                from app.models.invoice import InvoiceType

                invoice = await InvoiceService.create_invoice(
                    user=user,
                    subscription_id=str(sub.id),
                    plan_id=str(new_plan.id),
                    plan_name=new_plan.name,
                    plan_type=new_plan.plan_type,
                    invoice_type=InvoiceType.UPGRADE,
                    subtotal=amount_paid,
                    currency=currency,
                    payment_id=payment_id,
                    period_start=sub.started_at,
                    period_end=sub.expires_at,
                )
                await InvoiceService.send_invoice_email(
                    user=user,
                    invoice=invoice,
                    subject=_SUBJECT_UPGRADE,
                    extra_context={"subscriptionUpgraded": True},
                )

            await NotificationOrchestrator.notify_user(
                user_id=str(user.id),
                title="Plan Upgraded",
                body=f"Your plan has been upgraded to {new_plan.name}. New features are now available.",
                notification_type="SUBSCRIPTION_UPGRADED",
                background_tasks=background_tasks,
                data={
                    "plan_id":   str(new_plan.id),
                    "plan_name": new_plan.name,
                    "plan_type": new_plan.plan_type,
                },
                path="/subscriptions/current",
                send_in_app=True,
                send_push=True,
            )

            return sub

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to upgrade subscription user_id=%s", user_id
            )
            raise AppException("Failed to upgrade subscription", status_code=500)

    # ─────────────────────────────────────────
    # Renew
    # ─────────────────────────────────────────

    @staticmethod
    async def renew_subscription(
        user_id: str,
        background_tasks: BackgroundTasks,
        payment_id: Optional[str] = None,
        amount_paid: Optional[float] = None,
        currency: str = "USD",
    ) -> Union[ClientSubscription, ProviderSubscription]:
        try:
            user = await User.get(user_id)
            if not user or user.is_deleted:
                raise NotFoundException("User not found")

            PlanModel, SubModel = _get_models(user.user_type)

            existing = await SubscriptionService.get_active_subscription(
                user_id, user.user_type
            )

            if not existing:
                # Try to find most recent expired subscription
                existing = await SubModel.find_one(
                    SubModel.user_id == user_id,
                    SubModel.status  == SubscriptionStatus.EXPIRED,
                    SubModel.is_deleted == False,
                )
                if not existing:
                    raise NotFoundException(
                        "No subscription found to renew. Please subscribe first."
                    )

            plan = await PlanModel.get(existing.plan_id)
            if not plan or plan.is_deleted or not plan.is_active:
                raise NotFoundException(
                    "Your current plan is no longer available. Please choose a new plan."
                )

            if plan.price == 0.0:
                raise ValidationException("Free plans do not need renewal.")

            now       = _utc_now()
            new_start = (
                existing.expires_at
                if existing.status == SubscriptionStatus.ACTIVE and existing.expires_at
                else now
            )
            new_expiry = new_start + timedelta(days=plan.duration_days)

            renew_plan_id   = str(existing.plan_id)
            renew_plan_type = existing.plan_type

            existing.status              = SubscriptionStatus.CANCELLED
            existing.cancelled_at        = now
            existing.cancellation_reason = "Renewed"
            existing.updated_by          = user_id
            await existing.save()

            sub = SubModel(
                user_id=user_id,
                plan_id=renew_plan_id,
                plan_type=renew_plan_type,
                status=SubscriptionStatus.ACTIVE,
                started_at=new_start,
                expires_at=new_expiry,
                payment_id=payment_id or f"manual_{user_id}",
                amount_paid=amount_paid if amount_paid is not None else plan.price,
                currency=currency,
                features_snapshot=plan.features,
                created_by=user_id,
            )
            await sub.insert()

            user.subscription_plan       = sub.plan_type
            user.subscription_expires_at = sub.expires_at
            user.updated_by              = user_id
            await user.save()

            if amount_paid and amount_paid > 0:
                from app.services.invoice_service import InvoiceService
                from app.models.invoice import InvoiceType

                invoice = await InvoiceService.create_invoice(
                    user=user,
                    subscription_id=str(sub.id),
                    plan_id=renew_plan_id,
                    plan_name=plan.name,
                    plan_type=plan.plan_type,
                    invoice_type=InvoiceType.RENEWAL,
                    subtotal=amount_paid,
                    currency=currency,
                    payment_id=payment_id,
                    period_start=new_start,
                    period_end=new_expiry,
                )
                await InvoiceService.send_invoice_email(
                    user=user,
                    invoice=invoice,
                    subject=_SUBJECT_RENEW,
                    extra_context={"subscriptionRenewed": True},
                )

            await NotificationOrchestrator.notify_user(
                user_id=str(user.id),
                title="Subscription Renewed",
                body=f"Your {plan.name} plan has been renewed until {new_expiry.strftime('%d %B %Y')}.",
                notification_type="SUBSCRIPTION_RENEWED",
                background_tasks=background_tasks,
                data={
                    "plan_id":    renew_plan_id,
                    "plan_name":  plan.name,
                    "plan_type":  renew_plan_type,
                    "expires_at": str(new_expiry),
                },
                path="/subscriptions/current",
                send_in_app=True,
                send_push=True,
            )

            return sub

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to renew subscription user_id=%s", user_id
            )
            raise AppException("Failed to renew subscription", status_code=500)
    # ─────────────────────────────────────────
    # Cancel
    # ─────────────────────────────────────────

    @staticmethod
    async def cancel_subscription(
        user_id: str,
        background_tasks: BackgroundTasks,
        reason: Optional[str] = None,
    ) -> dict:
        try:
            user = await User.get(user_id)
            if not user or user.is_deleted:
                raise NotFoundException("User not found")

            sub = await SubscriptionService.get_active_subscription(
                user_id, user.user_type
            )
            if not sub:
                raise NotFoundException("No active subscription found")

            cancelled_at = _utc_now()
            plan_name    = sub.plan_type

            sub.status              = SubscriptionStatus.CANCELLED
            sub.cancelled_at        = cancelled_at
            sub.cancellation_reason = reason
            sub.updated_by          = user_id
            await sub.save()

            free_plan_type = (
                PlanType.CLIENT_FREE.value if user.user_type == UserRole.CLIENT
                else PlanType.PROVIDER_TIER1.value
            )
            user.subscription_plan       = free_plan_type
            user.subscription_expires_at = None
            user.updated_by              = user_id
            await user.save()

            await SubscriptionService._send_cancellation_email(
                user=user,
                plan_name=plan_name,
                cancelled_at=cancelled_at,
                reason=reason,
            )

            await NotificationOrchestrator.notify_user(
                user_id=str(user.id),
                title="Subscription Cancelled",
                body=f"Your {plan_name} plan has been cancelled. You have been moved to the free plan.",
                notification_type="SUBSCRIPTION_CANCELLED",
                background_tasks=background_tasks,
                data={
                    "plan_name": plan_name,
                    "reason":    reason or "Not specified",
                },
                path="/plans",
                send_in_app=True,
                send_push=True,
            )

            return {"message": "Subscription cancelled successfully"}

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to cancel subscription user_id=%s", user_id
            )
            raise AppException("Failed to cancel subscription", status_code=500)

    # ─────────────────────────────────────────
    # Activate — called by payment webhook
    # ─────────────────────────────────────────

    @staticmethod
    async def activate_subscription(
        user_id: str,
        plan_id: str,
        payment_id: str,
        amount_paid: float,
        background_tasks: BackgroundTasks,
        currency: str = "USD",
    ) -> Union[ClientSubscription, ProviderSubscription]:
        try:
            if not ObjectId.is_valid(plan_id):
                raise ValidationException("Invalid plan id")

            user = await User.get(user_id)
            if not user or user.is_deleted:
                raise NotFoundException("User not found")

            PlanModel, SubModel = _get_models(user.user_type)

            plan = await PlanModel.get(plan_id)
            if not plan or plan.is_deleted or not plan.is_active:
                raise NotFoundException("Plan not found or inactive")

            existing = await SubscriptionService.get_active_subscription(
                user_id, user.user_type
            )
            if existing:
                existing.status              = SubscriptionStatus.CANCELLED
                existing.cancelled_at        = _utc_now()
                existing.cancellation_reason = "Replaced by new subscription"
                existing.updated_by          = user_id
                await existing.save()

            now = _utc_now()
            sub = SubModel(
                user_id=user_id,
                plan_id=str(plan.id),
                plan_type=plan.plan_type,
                status=SubscriptionStatus.ACTIVE,
                started_at=now,
                expires_at=now + timedelta(days=plan.duration_days),
                payment_id=payment_id,
                amount_paid=amount_paid,
                currency=currency,
                features_snapshot=plan.features,
                created_by=user_id,
            )
            await sub.insert()

            user.subscription_plan       = plan.plan_type
            user.subscription_expires_at = sub.expires_at
            user.updated_by              = user_id
            await user.save()

            is_admin_grant = str(payment_id).startswith("admin_grant_")
            if not is_admin_grant and amount_paid > 0:
                from app.services.invoice_service import InvoiceService
                from app.models.invoice import InvoiceType

                invoice = await InvoiceService.create_invoice(
                    user=user,
                    subscription_id=str(sub.id),
                    plan_id=str(plan.id),
                    plan_name=plan.name,
                    plan_type=plan.plan_type,
                    invoice_type=InvoiceType.NEW_SUBSCRIPTION,
                    subtotal=amount_paid,
                    currency=currency,
                    payment_id=payment_id,
                    period_start=sub.started_at,
                    period_end=sub.expires_at,
                )
                await InvoiceService.send_invoice_email(
                    user=user,
                    invoice=invoice,
                    subject=_SUBJECT_NEW,
                    extra_context={"subscriptionConfirmed": True},
                )

            await NotificationOrchestrator.notify_user(
                user_id=str(user.id),
                title="Subscription Activated",
                body=f"Your {plan.name} plan is now active. Enjoy your features!",
                notification_type="SUBSCRIPTION_ACTIVATED",
                background_tasks=background_tasks,
                data={
                    "plan_id":   str(plan.id),
                    "plan_name": plan.name,
                    "plan_type": plan.plan_type,
                },
                path="/subscriptions/current",
                send_in_app=True,
                send_push=True,
            )

            return sub

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to activate subscription user_id=%s", user_id
            )
            raise AppException("Failed to activate subscription", status_code=500)

    # ─────────────────────────────────────────
    # Admin — manual grant
    # ─────────────────────────────────────────

    @staticmethod
    async def admin_grant(
        user_id: str,
        plan_id: str,
        admin_id: str,
        background_tasks: BackgroundTasks,
    ) -> Union[ClientSubscription, ProviderSubscription]:
        return await SubscriptionService.activate_subscription(
            user_id=user_id,
            plan_id=plan_id,
            payment_id=f"admin_grant_{admin_id}",
            amount_paid=0.0,
            background_tasks=background_tasks,
        )

# ─────────────────────────────────────────────────────────────────────────────
# Warn expiring subscriptions — run daily at 9am
# ─────────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def warn_expiring_subscriptions() -> int:
        try:
            now = _utc_now()
            in_3days = now + timedelta(days=1)
            count = 0

            for SubModel in [ClientSubscription, ProviderSubscription]:
                collection = SubModel.get_pymongo_collection()
                expiring_soon = await collection.find({
                    "status": SubscriptionStatus.ACTIVE,
                    "expires_at": {"$gte": now, "$lte": in_3days},
                    "is_deleted": False,
                }).to_list(None)

                for sub in expiring_soon:
                    try:
                        user = await User.get(sub["user_id"])
                        if user:
                            expires_at = sub.get("expires_at")
                            expiry_str = expires_at.strftime("%d %B %Y") if expires_at else "soon"

                            # Send push
                            await NotificationOrchestrator.notify_user(
                                user_id=str(user.id),
                                title="Subscription Expiring Soon",
                                body=f"Your subscription expires on {expiry_str}. Renew now to avoid interruption.",
                                notification_type="SUBSCRIPTION_EXPIRING_SOON",
                                background_tasks=None,
                                data={"expires_at": str(expires_at)},
                                path="/subscriptions/renew",
                                send_in_app=True,
                                send_push=True,
                            )

                            # Send email
                            # Determine which plan model to use based on SubModel
                            if SubModel == ClientSubscription:
                                plan = await ClientPlan.get(sub["plan_id"])
                            else:
                                plan = await ProviderPlan.get(sub["plan_id"])

                            plan_name = plan.name if plan else sub["plan_type"]

                            await send_mail(
                                {
                                    "to": user.email,
                                    "subject": f"Your {plan_name} plan expires in 3 days"
                                },
                                {
                                    "name": user.fname or user.business_name or user.full_name or "User",
                                    "plan_name": plan_name,
                                    "expiry_date": expiry_str,
                                    "renew_link": f"{settings.FRONTEND_URL}/subscriptions/renew",
                                },
                                "subscription-expiring.html",
                            )
                            count += 1
                    except Exception as e:
                        app_logger.error("Expiry warning failed user_id=%s: %s", sub.get("user_id"), e)

            if not count:
                app_logger.info("No subscriptions expiring in 3 days")
            else:
                app_logger.info("Sent expiry warnings to %d users", count)
            return count
        except Exception:
            app_logger.exception("Failed to send expiry warnings")
            return 0


    # ─────────────────────────────────────────────────────────────────────────────
    # Expiry cron — run daily at midnight
    # ─────────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def expire_stale_subscriptions() -> int:
        try:
            now = _utc_now()
            count = 0

            for SubModel in [ClientSubscription, ProviderSubscription]:
                collection = SubModel.get_pymongo_collection()

                expiring = await collection.find({
                    "status": SubscriptionStatus.ACTIVE,
                    "expires_at": {"$lt": now, "$ne": None},
                    "is_deleted": False,
                }).to_list(None)

                if not expiring:
                    continue

                result = await collection.update_many(
                    {
                        "status": SubscriptionStatus.ACTIVE,
                        "expires_at": {"$lt": now, "$ne": None},
                        "is_deleted": False,
                    },
                    {"$set": {
                        "status": SubscriptionStatus.EXPIRED,
                        "updated_at": now,
                    }},
                )
                count += result.modified_count

                for sub in expiring:
                    try:
                        user = await User.get(sub["user_id"])
                        if user:
                            # Send push
                            await NotificationOrchestrator.notify_user(
                                user_id=str(user.id),
                                title="Subscription Expired",
                                body="Your subscription has expired. Renew now to keep your features.",
                                notification_type="SUBSCRIPTION_EXPIRED",
                                background_tasks=None,
                                data={"plan_type": sub.get("plan_type", "")},
                                path="/subscriptions/renew",
                                send_in_app=True,
                                send_push=True,
                            )

                            # Send email
                            if SubModel == ClientSubscription:
                                plan = await ClientPlan.get(sub["plan_id"])
                            else:
                                plan = await ProviderPlan.get(sub["plan_id"])

                            plan_name = plan.name if plan else sub["plan_type"]
                            expiry_date = sub.get("expires_at")
                            expiry_str = expiry_date.strftime("%d %B %Y") if expiry_date else "recently"

                            await send_mail(
                                {
                                    "to": user.email,
                                    "subject": f"Your {plan_name} plan has expired"
                                },
                                {
                                    "name": user.fname or user.business_name or user.full_name or "User",
                                    "plan_name": plan_name,
                                    "expiry_date": expiry_str,
                                    "renew_link": f"{settings.FRONTEND_URL}/subscriptions/renew",
                                },
                                "subscription-expired.html",
                            )
                    except Exception as e:
                        app_logger.error("Expiry notification failed user_id=%s: %s", sub.get("user_id"), e)

            if count:
                app_logger.info("Expired %d subscriptions", count)
            return count
        except Exception:
            app_logger.exception("Failed to expire subscriptions")
            raise AppException("Failed to expire subscriptions", status_code=500)


    @staticmethod
    async def get_current_subscription_response(
        user_id:   str,
        user_type: UserRole,
    ) -> dict:
        """
        Builds the full current subscription response.
        Called by GET /subscriptions/current endpoint.
        All logic in service — endpoint just calls this.
        """
        from app.schemas.subscription import MySubscriptionDataResponse

        sub      = await SubscriptionService.get_active_subscription(user_id, user_type)
        features = await SubscriptionService.get_user_features(user_id, user_type)

        if not sub:
            data = MySubscriptionDataResponse(
                plan_type=f"{'client_free' if user_type == UserRole.CLIENT else 'provider_tier1'}",
                status=SubscriptionStatus.EXPIRED,
                expires_at=None,
                features=features,
                is_active=False,
            )
        else:
            data = MySubscriptionDataResponse(
                plan_type=sub.plan_type,
                status=sub.status,
                expires_at=sub.expires_at,
                features=sub.features_snapshot,
                is_active=True,
            )

        return data