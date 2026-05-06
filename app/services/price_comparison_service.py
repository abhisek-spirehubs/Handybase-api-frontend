from __future__ import annotations

import re
from typing import List, Optional

from bson import ObjectId

from app.core.exceptions import AppException, ValidationException
from app.models.service import Service, ServiceApprovalStatus
from app.models.user import User
from app.schemas.client_features import ProviderPriceSummary
from app.utils.logger import app_logger


async def compare_prices(
    category_id: Optional[str],
    search: Optional[str],
    city: Optional[str],
    state: Optional[str],
    min_price: Optional[float],
    max_price: Optional[float],
    sort_by: str = "price_low",
    page: int = 1,
    limit: int = 20,
) -> dict:
    """
    Fetch approved active services with provider details for price comparison.

    Args:
        category_id: Filter by category ID.
        search: Text search (title/description) – uses MongoDB $text index.
        city: Filter by city (case‑insensitive).
        state: Filter by state (case‑insensitive).
        min_price, max_price: Price range.
        sort_by: "price_low", "price_high", "top_rated", "newest".
        page, limit: Pagination.

    Returns:
        PriceComparisonResponse containing total count and list of results.
    """
    try:
        skip = (page - 1) * limit
        query: dict = {
            "is_deleted": False,
            "approval_status": ServiceApprovalStatus.APPROVED,
            "is_active": True,
        }

        # ---- Filters ----
        if category_id:
            if not ObjectId.is_valid(category_id):
                raise ValidationException("Invalid category id")
            obj_id = ObjectId(category_id)
            query["category_id"] = {"$in": [category_id, obj_id]}

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
            # Requires a text index on title and description
            query["$text"] = {"$search": search}

        # ---- Sorting ----
        sort_map = {
            "price_low":  [("price", 1)],
            "price_high": [("price", -1)],
            "newest":     [("created_at", -1)],
        }
        sort = sort_map.get(sort_by, sort_map["price_low"])

        # ---- Pagination ----
        total = await Service.find(query).count()
        services = (
            await Service.find(query)
            .sort(sort)
            .skip(skip)
            .limit(limit)
            .to_list()
        )

        # ---- Fetch providers for these services ----
        provider_ids = {str(s.provider_id) for s in services}
        providers = {}
        if provider_ids:
            object_ids = [ObjectId(pid) for pid in provider_ids if ObjectId.is_valid(pid)]
            if object_ids:
                provider_docs = await User.find({"_id": {"$in": object_ids}}).to_list()
                providers = {str(p.id): p for p in provider_docs}

        # ---- Build result list ----
        results: List[ProviderPriceSummary] = []
        for service in services:
            provider = providers.get(service.provider_id)
            if provider:
                # Use getattr for safety (some fields might be missing)
                fname = getattr(provider, "fname", "") or ""
                lname = getattr(provider, "lname", "") or ""
                business_name = getattr(provider, "business_name", None)
                profile_image = getattr(provider, "profile_image", None)
                rating = getattr(provider, "rating", 0.0) or 0.0
                total_reviews = getattr(provider, "total_reviews", 0) or 0
                # Priority flag may be named either way
                has_priority = getattr(provider, "has_priority", False) or getattr(provider, "has_priority_listing", False)
                provider_name = (f"{fname} {lname}".strip() or business_name or "Unknown")
            else:
                business_name = None
                profile_image = None
                rating = 0.0
                total_reviews = 0
                has_priority = False
                provider_name = "Unknown"

            results.append(
                ProviderPriceSummary(
                    provider_id=str(service.provider_id),
                    provider_name=provider_name,
                    business_name=business_name,
                    profile_image=profile_image,
                    rating=rating,
                    total_reviews=total_reviews,
                    has_priority=has_priority,
                    service_id=str(service.id),
                    service_title=service.title,
                    service_price=service.price,
                    service_duration=service.duration,
                    city=service.city,
                    state=service.state,
                    images=service.images,
                )
            )

        # Apply in‑memory sorting for top_rated
        if sort_by == "top_rated":
            results.sort(key=lambda x: x.rating, reverse=True)

        return {
            "total": total,
            "results": results,
        }

    except AppException:
        raise
    except Exception:
        app_logger.exception("Failed to compare prices")
        raise AppException("Failed to fetch price comparison", status_code=500)