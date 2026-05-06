from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from typing import Optional

from app.dependencies.auth import get_current_user
from app.models.user import User, UserRole
from app.schemas.invoice import InvoiceResponse, InvoiceListResponse
from app.services.invoice_service import InvoiceService

router = APIRouter()


@router.get(
    "",
    response_model=InvoiceListResponse,
    summary="Get invoices — user sees own, admin sees all",
)
async def get_invoices(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    user_id: Optional[str] = Query(None, description="[ADMIN only] filter by user"),
    current_user: User = Depends(get_current_user),
):
    # Admin can filter by any user_id
    # Regular user always gets only their own
    target_user_id = (
        user_id
        if current_user.user_type == UserRole.ADMIN and user_id
        else str(current_user.id)
    )
    return await InvoiceService.get_user_invoices(
        user_id=target_user_id,
        page=page,
        limit=limit,
    )


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Get single invoice — user sees own, admin sees any",
)
async def get_invoice(
    invoice_id: str,
    current_user: User = Depends(get_current_user),
):
    # Admin can fetch any invoice
    # User can only fetch their own — enforced inside service
    if current_user.user_type == UserRole.ADMIN:
        from bson import ObjectId
        from app.core.exceptions import ValidationException, NotFoundException
        from app.models.invoice import Invoice

        if not ObjectId.is_valid(invoice_id):
            raise ValidationException("Invalid invoice id")

        invoice = await Invoice.get(invoice_id)
        if not invoice or invoice.is_deleted:
            raise NotFoundException("Invoice not found")

        return invoice

    return await InvoiceService.get_invoice_by_id(
        invoice_id=invoice_id,
        user_id=str(current_user.id),
    )


@router.get(
    "/{invoice_id}/pdf",
    summary="Download invoice as PDF — user downloads own, admin downloads any",
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "PDF invoice file",
        }
    },
)
async def download_invoice_pdf(
    invoice_id: str,
    current_user: User = Depends(get_current_user),
):
    from bson import ObjectId
    from app.core.exceptions import ValidationException, NotFoundException
    from app.models.invoice import Invoice

    if current_user.user_type == UserRole.ADMIN:
        if not ObjectId.is_valid(invoice_id):
            raise ValidationException("Invalid invoice id")
        invoice = await Invoice.get(invoice_id)
        if not invoice or invoice.is_deleted:
            raise NotFoundException("Invoice not found")
    else:
        invoice = await InvoiceService.get_invoice_by_id(
            invoice_id=invoice_id,
            user_id=str(current_user.id),
        )

    pdf_bytes = InvoiceService.generate_pdf(invoice)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f"attachment; filename=invoice-{invoice.invoice_number}.pdf"
            ),
        },
    )