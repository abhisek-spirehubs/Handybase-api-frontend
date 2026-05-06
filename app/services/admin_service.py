import re
from datetime import datetime
from typing import Optional

from app.models.user import User, UserRole
from app.models.booking import Booking, BookingStatus
from app.models.service import Service
from app.utils.logger import app_logger
from app.core.exceptions import AppException


class AdminService:

    # ─────────────────────────────────────────
    # User management
    # ─────────────────────────────────────────
    @staticmethod
    async def get_all_users(
        page:   int,
        limit:  int,
        role:   Optional[str] = None,
        search: Optional[str] = None,
    ) -> dict:
        try:
            skip = (page - 1) * limit
            query: dict = {"is_deleted": False}

            if role:
                query["user_type"] = role

            if search:
                # Use regex for flexible search (can be improved with text index if needed)
                pattern = re.compile(re.escape(search), re.IGNORECASE)
                query["$or"] = [
                    {"fname": {"$regex": pattern}},
                    {"lname": {"$regex": pattern}},
                    {"email": {"$regex": pattern}},
                ]

            # 1. Count total matching documents (fast, index‑only if possible)
            total = await User.find(query).count()

            # 2. Fetch only the required page (sort, skip, limit)
            data = await User.find(query) \
                .sort("-created_at") \
                .skip(skip) \
                .limit(limit) \
                .to_list()

            pages = max(1, (total + limit - 1) // limit)

            return {
                "total":    total,
                "page":     page,
                "limit":    limit,
                "pages":    pages,
                "has_next": page < pages,
                "has_prev": page > 1,
                "data":     data,
            }

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to fetch users")
            raise AppException("Failed to fetch users", status_code=500)

    # ─────────────────────────────────────────
    # Dashboard stats
    # ─────────────────────────────────────────

    @staticmethod
    async def get_dashboard_stats() -> dict:
        try:
            # ── User counts ───────────────────────────────────────────────
            total_clients = await User.find(
                User.user_type  == UserRole.CLIENT,
                User.is_deleted == False,
            ).count()

            total_providers = await User.find(
                User.user_type  == UserRole.PROVIDER,
                User.is_deleted == False,
            ).count()

            pending_providers = await User.find(
                User.user_type           == UserRole.PROVIDER,
                User.is_provider_approved == False,
                User.is_deleted          == False,
            ).count()

            # ── Booking counts ────────────────────────────────────────────
            total_bookings = await Booking.find(
                Booking.is_deleted == False
            ).count()

            pending_bookings = await Booking.find(
                Booking.booking_status == BookingStatus.PENDING,
                Booking.is_deleted     == False,
            ).count()

            confirmed_bookings = await Booking.find(
                Booking.booking_status == BookingStatus.CONFIRMED,
                Booking.is_deleted     == False,
            ).count()

            completed_bookings = await Booking.find(
                Booking.booking_status == BookingStatus.COMPLETED,
                Booking.is_deleted     == False,
            ).count()

            cancelled_bookings = await Booking.find(
                Booking.booking_status == BookingStatus.CANCELLED,
                Booking.is_deleted     == False,
            ).count()

            # ── Service counts ────────────────────────────────────────────
            total_services = await Service.find(
                Service.is_deleted == False
            ).count()

            pending_services = await Service.find(
                {"approval_status": "PENDING"},
                Service.is_deleted == False,
            ).count()

            # ── Revenue (completed bookings only) ─────────────────────────
            collection = Booking.get_pymongo_collection()
            revenue_result = await collection.aggregate([
                {
                    "$match": {
                        "booking_status": BookingStatus.COMPLETED,
                        "is_deleted":     False,
                    }
                },
                {
                    "$group": {
                        "_id":           None,
                        "total_revenue": {"$sum": "$total_amount"},
                    }
                },
            ]).to_list(length=1)

            total_revenue = (
                revenue_result[0]["total_revenue"]
                if revenue_result else 0.0
            )

            return {
                "users": {
                    "total_clients":      total_clients,
                    "total_providers":    total_providers,
                    "pending_approvals":  pending_providers,
                },
                "bookings": {
                    "total":     total_bookings,
                    "pending":   pending_bookings,
                    "confirmed": confirmed_bookings,
                    "completed": completed_bookings,
                    "cancelled": cancelled_bookings,
                },
                "services": {
                    "total":   total_services,
                    "pending": pending_services,
                },
                "revenue": {
                    "total":    round(total_revenue, 2),
                    "currency": "USD",
                },
                "generated_at": datetime.utcnow().isoformat(),
            }

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to fetch dashboard stats")
            raise AppException("Failed to fetch dashboard stats", status_code=500)