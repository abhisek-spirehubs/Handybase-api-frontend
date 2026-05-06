from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.dependencies.subscription import require_feature
from app.models.user import User, UserRole
from app.schemas.financial_report import FinancialSummarySchema
from app.schemas.common import APIResponse
from app.services import financial_report
from app.core.exceptions import (
    ValidationException,
    ForbiddenException,
    ServiceUnavailableException,
)

router = APIRouter()

_VALID_PERIODS = {"week", "month", "quarter", "custom"}


# ─────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────

def _validate_period(
    period: str,
    date_from: Optional[date],
    date_to: Optional[date],
) -> None:

    if period not in _VALID_PERIODS:
        raise ValidationException(
            errors=[{
                "field": "period",
                "message": f"Must be one of: {', '.join(_VALID_PERIODS)}"
            }]
        )

    if period == "custom" and (not date_from or not date_to):
        raise ValidationException(
            errors=[{
                "field": "date_from/date_to",
                "message": "Both required when period=custom"
            }]
        )


# ─────────────────────────────────────────
# FINANCIAL SUMMARY
# ─────────────────────────────────────────

@router.get(
    "/summary",
    response_model=APIResponse[FinancialSummarySchema],
    summary="Earnings summary for a selected period (Tier 3)",
)
async def get_financial_summary(
    period: str = Query(default="month"),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    current_user: User = Depends(require_feature("can_view_analytics")),
):
    """
    Returns earnings summary:
    - total earnings
    - completed jobs
    - tax collected
    - avg earning
    - itemised bookings
    """

    if current_user.user_type != UserRole.PROVIDER:
        raise ForbiddenException("Only providers can access financial reports")

    _validate_period(period, date_from, date_to)

    try:
        summary = await financial_report.compute_financial_summary(
            provider_id=str(current_user.id),
            period=period,
            date_from=date_from,
            date_to=date_to,
        )

        return APIResponse(
            message="Financial summary fetched successfully",
            data=summary,
        )

    except ValueError as e:
        raise ValidationException(
            errors=[{
                "field": None,
                "message": str(e)
            }]
        )


# ─────────────────────────────────────────
# PDF DOWNLOAD
# ─────────────────────────────────────────

@router.get(
    "/report/download",
    summary="Download financial report as PDF (Tier 3)",
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "PDF financial report",
        }
    },
)
async def download_financial_report(
    period: str = Query(default="month"),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    current_user: User = Depends(require_feature("can_view_analytics")),
):
    """
    Streams PDF financial report.
    """

    if current_user.user_type != UserRole.PROVIDER:
        raise ForbiddenException("Only providers can download financial reports")

    _validate_period(period, date_from, date_to)

    provider_name = (
        current_user.business_name
        or current_user.full_name
        or current_user.fname
        or "Provider"
    )

    try:
        pdf_bytes = await financial_report.generate_financial_report_pdf(
            provider_id=str(current_user.id),
            provider_name=provider_name,
            period=period,
            date_from=date_from,
            date_to=date_to,
        )

    except ValueError as e:
        raise ValidationException(
            errors=[{
                "field": None,
                "message": str(e)
            }]
        )

    except RuntimeError as e:
        raise ServiceUnavailableException(str(e))

    filename = f"financial_report_{period}_{date.today()}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )