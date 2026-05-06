from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, status

from app.dependencies.auth import get_current_user
from app.dependencies.subscription import require_feature
from app.models.quotation import QuotationStatus
from app.models.user import User, UserRole
from app.schemas.client_features import (
    ProviderPriceSummary,
    QuotationCreate,
    QuotationDecision,
    QuotationRespond,
    QuotationDataResponse,
)
from app.schemas.common import APIResponse, PaginatedResponse, MessageResponse
from app.services import price_comparison_service, quotation_service
from app.core.exceptions import ForbiddenException

router = APIRouter()


# ── Price Comparison ─────────────────────────────────────────

@router.get(
    "/client/compare-prices",
    response_model=APIResponse[PaginatedResponse[ProviderPriceSummary]],
)
async def compare_prices(
    category_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    sort_by: str = Query("price_low"),
    page: int = Query(1),
    limit: int = Query(20),
    current_user: User = Depends(get_current_user),  # ✅ FIX
):
    # ✅ STEP 1: ROLE CHECK FIRST
    if current_user.user_type != UserRole.CLIENT:
        raise ForbiddenException("Only clients can compare prices.")

    # ✅ STEP 2: FEATURE CHECK AFTER ROLE
    from app.services.subscription_service import SubscriptionService

    features = await SubscriptionService.get_user_features(
        user_id=str(current_user.id),
        user_type=current_user.user_type,
    )

    if not getattr(features, "can_compare_prices", False):
        raise ForbiddenException(
            "Your current plan does not include this feature. Please upgrade."
        )

    # ✅ BUSINESS LOGIC
    result = await price_comparison_service.compare_prices(
        category_id=category_id,
        search=search,
        city=city,
        state=state,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
        page=page,
        limit=limit,
    )

    return APIResponse(
        message="Price comparison fetched successfully",
        data=PaginatedResponse(
            message="Price comparison fetched successfully",
            total=result["total"],
            data=result["results"],
        ),
    )


# ── CLIENT: CREATE ─────────────────────────────────────────

@router.post(
    "/client/quotations",
    response_model=APIResponse[QuotationDataResponse],
    status_code=status.HTTP_201_CREATED,
)
async def request_quotation(
    data: QuotationCreate,
    current_user: User = Depends(require_feature("can_request_quotes")),
):
    if current_user.user_type != UserRole.CLIENT:
        raise ForbiddenException("Only clients can request quotations.")

    quotation = await quotation_service.create_quotation(
        client=current_user,
        data=data,
    )

    return APIResponse(
        message="Quotation request sent successfully",
        data=quotation,
    )


# ── CLIENT: LIST ─────────────────────────────────────────

@router.get(
    "/client/quotations",
    response_model=PaginatedResponse[QuotationDataResponse],
)
async def list_my_quotations(
    status_filter: Optional[QuotationStatus] = Query(None, alias="status"),
    page: int = Query(1),
    limit: int = Query(10),
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type != UserRole.CLIENT:
        raise ForbiddenException("Only clients can access this.")

    result = await quotation_service.get_client_quotations(
        client_id=str(current_user.id),
        status_filter=status_filter,
        page=page,
        limit=limit,
    )

    return PaginatedResponse(
        message="Quotations fetched successfully",
        total=result["total"],
        data=result["data"],
    )


# ── CLIENT: GET SINGLE ─────────────────────────────────────────

@router.get(
    "/client/quotations/{quotation_id}",
    response_model=APIResponse[QuotationDataResponse],
)
async def get_quotation(
    quotation_id: str,
    current_user: User = Depends(get_current_user),
):
    quotation = await quotation_service.get_quotation_by_id(
        user=current_user,
        quotation_id=quotation_id,
    )

    return APIResponse(
        message="Quotation fetched successfully",
        data=quotation,
    )


# ── CLIENT: CANCEL ─────────────────────────────────────────

@router.post(
    "/client/quotations/{quotation_id}/cancel",
    response_model=APIResponse[QuotationDataResponse],
)
async def cancel_quotation(
    quotation_id: str,
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type != UserRole.CLIENT:
        raise ForbiddenException("Only clients can cancel quotations.")

    quotation = await quotation_service.cancel_quotation(
        client=current_user,
        quotation_id=quotation_id,
    )

    return APIResponse(
        message="Quotation cancelled successfully",
        data=quotation,
    )


# ── CLIENT: DECIDE ─────────────────────────────────────────

@router.post(
    "/client/quotations/{quotation_id}/decide",
    response_model=APIResponse[QuotationDataResponse],
)
async def decide_quotation(
    quotation_id: str,
    data: QuotationDecision,
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type != UserRole.CLIENT:
        raise ForbiddenException("Only clients can decide quotations.")

    quotation = await quotation_service.decide_quotation(
        client=current_user,
        quotation_id=quotation_id,
        data=data,
    )

    msg = (
        "Quotation accepted — booking created successfully"
        if data.accept
        else "Quotation rejected"
    )

    return APIResponse(message=msg, data=quotation)


# ── PROVIDER: LIST ─────────────────────────────────────────

@router.get(
    "/provider/quotations",
    response_model=PaginatedResponse[QuotationDataResponse],
)
async def list_provider_quotations(
    status_filter: Optional[QuotationStatus] = Query(None, alias="status"),
    page: int = Query(1),
    limit: int = Query(10),
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type != UserRole.PROVIDER:
        raise ForbiddenException("Only providers can access this.")

    result = await quotation_service.get_provider_quotations(
        provider_id=str(current_user.id),
        status_filter=status_filter,
        page=page,
        limit=limit,
    )

    return PaginatedResponse(
        message="Quotations fetched successfully",
        total=result["total"],
        data=result["data"],
    )


# ── PROVIDER: RESPOND ─────────────────────────────────────────

@router.post(
    "/provider/quotations/{quotation_id}/respond",
    response_model=APIResponse[QuotationDataResponse],
)
async def respond_to_quotation(
    quotation_id: str,
    data: QuotationRespond,
    current_user: User = Depends(get_current_user),
):
    if current_user.user_type != UserRole.PROVIDER:
        raise ForbiddenException("Only providers can respond.")

    quotation = await quotation_service.respond_to_quotation(
        provider=current_user,
        quotation_id=quotation_id,
        data=data,
    )

    return APIResponse(
        message="Quotation response sent successfully",
        data=quotation,
    )