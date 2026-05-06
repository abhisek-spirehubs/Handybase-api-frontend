from bson import ObjectId
from typing import Optional

from app.models.client_plan import ClientPlan
from app.models.provider_plan import ProviderPlan
from app.models.plan import PlanFeatures
from app.models.user import UserRole
from app.utils.logger import app_logger
from app.core.exceptions import (
    NotFoundException,
    ValidationException,
    AppException,
)

# ── Client plan types ─────────────────────────────────────────────────────────
_CLIENT_PLAN_TYPES   = {"client_free", "client_paid"}
_PROVIDER_PLAN_TYPES = {"provider_tier1", "provider_tier2", "provider_tier3"}


def _get_plan_model(plan_type: str):
    """Returns correct plan model based on plan_type string."""
    if plan_type in _CLIENT_PLAN_TYPES:
        return ClientPlan
    if plan_type in _PROVIDER_PLAN_TYPES:
        return ProviderPlan
    raise ValidationException(
        f"Invalid plan_type '{plan_type}'. "
        f"Must be one of: {_CLIENT_PLAN_TYPES | _PROVIDER_PLAN_TYPES}"
    )


class PlanService:
    """Plan management — CRUD + role-aware queries."""

    # ─────────────────────────────────────────
    # Create
    # ─────────────────────────────────────────

    @staticmethod
    async def create_client_plan(data: dict, admin_id: str) -> ClientPlan:
        try:
            plan = ClientPlan(**data, created_by=admin_id)
            await plan.insert()
            app_logger.info("Client plan created: %s", plan.plan_type)
            return plan
        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to create client plan")
            raise AppException("Failed to create client plan", status_code=500)

    @staticmethod
    async def create_provider_plan(data: dict, admin_id: str) -> ProviderPlan:
        try:
            plan = ProviderPlan(**data, created_by=admin_id)
            await plan.insert()
            app_logger.info("Provider plan created: %s", plan.plan_type)
            return plan
        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to create provider plan")
            raise AppException("Failed to create provider plan", status_code=500)

    # ─────────────────────────────────────────
    # Read — role-aware
    # ─────────────────────────────────────────

    @staticmethod
    async def get_client_plans(
        is_admin: bool = False,
        is_active: Optional[bool] = None,
        plan_type: Optional[str] = None,
    ) -> list:
        """
        Returns client plans.
        Public → active only.
        Admin  → all, filterable.
        """
        try:
            query = ClientPlan.find(ClientPlan.is_deleted == False)

            if not is_admin:
                query = query.find(ClientPlan.is_active == True)
            else:
                if is_active is not None:
                    query = query.find(ClientPlan.is_active == is_active)

            if plan_type:
                query = query.find({"plan_type": plan_type})

            return await query.sort("price").to_list()

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to fetch client plans")
            raise AppException("Failed to fetch client plans", status_code=500)

    @staticmethod
    async def get_provider_plans(
        is_admin: bool = False,
        is_active: Optional[bool] = None,
        plan_type: Optional[str] = None,
    ) -> list:
        """
        Returns provider plans.
        Public → active only.
        Admin  → all, filterable.
        """
        try:
            query = ProviderPlan.find(ProviderPlan.is_deleted == False)

            if not is_admin:
                query = query.find(ProviderPlan.is_active == True)
            else:
                if is_active is not None:
                    query = query.find(ProviderPlan.is_active == is_active)

            if plan_type:
                query = query.find({"plan_type": plan_type})

            return await query.sort("price").to_list()

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to fetch provider plans")
            raise AppException("Failed to fetch provider plans", status_code=500)

    @staticmethod
    async def get_plan_by_id(plan_id: str, plan_type: Optional[str] = None):
        """
        Fetches a plan by ID from correct collection.
        plan_type hint speeds up lookup — skips wrong collection.
        """
        try:
            if not ObjectId.is_valid(plan_id):
                raise ValidationException("Invalid plan id")

            # Try client plans first if no hint or hint is client
            if plan_type is None or plan_type in _CLIENT_PLAN_TYPES:
                plan = await ClientPlan.get(plan_id)
                if plan and not plan.is_deleted:
                    return plan

            # Try provider plans
            if plan_type is None or plan_type in _PROVIDER_PLAN_TYPES:
                plan = await ProviderPlan.get(plan_id)
                if plan and not plan.is_deleted:
                    return plan

            raise NotFoundException("Plan not found")

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to fetch plan id=%s", plan_id)
            raise AppException("Failed to fetch plan", status_code=500)

    # ─────────────────────────────────────────
    # Update
    # ─────────────────────────────────────────

    @staticmethod
    async def update_plan(plan_id: str, data: dict, admin_id: str):
        """Updates a plan in the correct collection."""
        try:
            if not ObjectId.is_valid(plan_id):
                raise ValidationException("Invalid plan id")

            # Try client plans first
            plan = await ClientPlan.get(plan_id)
            if not plan or plan.is_deleted:
                # Try provider plans
                plan = await ProviderPlan.get(plan_id)

            if not plan or plan.is_deleted:
                raise NotFoundException("Plan not found")

            for field, value in data.items():
                setattr(plan, field, value)

            plan.updated_by = admin_id
            await plan.save()
            return plan

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to update plan id=%s", plan_id)
            raise AppException("Failed to update plan", status_code=500)

    # ─────────────────────────────────────────
    # Delete
    # ─────────────────────────────────────────

    @staticmethod
    async def delete_plan(plan_id: str, admin_id: str) -> dict:
        """Soft-deletes a plan from correct collection."""
        try:
            if not ObjectId.is_valid(plan_id):
                raise ValidationException("Invalid plan id")

            # Try client plans first
            plan = await ClientPlan.get(plan_id)
            if not plan or plan.is_deleted:
                plan = await ProviderPlan.get(plan_id)

            if not plan or plan.is_deleted:
                raise NotFoundException("Plan not found")

            await plan.soft_delete(admin_id)
            return {"success": True, "message": "Plan deleted successfully"}

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to delete plan id=%s", plan_id)
            raise AppException("Failed to delete plan", status_code=500)