import io
from datetime import datetime
from typing import Optional

from app.models.invoice import Invoice, InvoiceStatus, InvoiceType
from app.models.user import User, UserRole
from app.utils.logger import app_logger
from app.core.exceptions import (
    AppException,
    NotFoundException,
    ValidationException,
    ForbiddenException,
)


class InvoiceService:

    # ─────────────────────────────────────────
    # Invoice number — HB-2026-000001
    # ─────────────────────────────────────────

    @staticmethod
    async def _generate_invoice_number() -> str:
        year = datetime.utcnow().year
        collection = Invoice.get_pymongo_collection()
        count = await collection.count_documents({"is_deleted": False})
        return f"HB-{year}-{str(count + 1).zfill(6)}"

    # ─────────────────────────────────────────
    # Create invoice
    # ─────────────────────────────────────────

    @staticmethod
    async def create_invoice(
        user: User,
        subscription_id: str,
        plan_id: str,
        plan_name: str,
        plan_type: str,
        invoice_type: InvoiceType,
        subtotal: float,
        tax_rate: float = 0.0,
        currency: str = "USD",
        payment_id: Optional[str] = None,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> Invoice:
        try:
            tax_amount = round(subtotal * tax_rate, 2)
            total      = round(subtotal + tax_amount, 2)

            invoice_number = await InvoiceService._generate_invoice_number()

            invoice = Invoice(
                invoice_number=invoice_number,
                user_id=str(user.id),
                subscription_id=subscription_id,
                plan_id=plan_id,
                plan_name=plan_name,
                plan_type=plan_type,
                invoice_type=invoice_type,
                subtotal=subtotal,
                tax_rate=tax_rate,
                tax_amount=tax_amount,
                total=total,
                currency=currency,
                payment_id=payment_id,
                # ── Fixed: always PAID on creation ───────────────────
                # Free plans never reach create_invoice (skipped in
                # subscription_service). VOID is admin-only action.
                status=InvoiceStatus.PAID,
                # ─────────────────────────────────────────────────────
                period_start=period_start,
                period_end=period_end,
                billing_name=user.full_name or user.fname or "User",
                billing_email=user.email,
                created_by=str(user.id),
            )

            await invoice.insert()

            app_logger.info(
                "Invoice created number=%s user_id=%s type=%s total=%s",
                invoice_number, str(user.id), invoice_type, total,
            )

            return invoice

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to create invoice user_id=%s", str(user.id)
            )
            raise AppException("Failed to generate invoice", status_code=500)

    # ─────────────────────────────────────────
    # Generate PDF bytes
    # ─────────────────────────────────────────

    @staticmethod
    def generate_pdf(invoice: Invoice) -> bytes:
        """
        Generates PDF bytes for an invoice.
        Returns raw bytes — used for email attachment or download.
        """
        from app.utils.pdf_generator import generate_invoice_pdf
        return generate_invoice_pdf(invoice)

    # ─────────────────────────────────────────
    # Send invoice email with PDF attachment
    # ─────────────────────────────────────────

    @staticmethod
    async def send_invoice_email(
        user: User,
        invoice: Invoice,
        subject: str,
        extra_context: Optional[dict] = None,
    ) -> None:
        """
        Sends invoice email with PDF attached.
        Never raises — email failure must never block subscription flow.
        """
        try:
            from app.utils.email import send_mail_with_attachment

            pdf_bytes = InvoiceService.generate_pdf(invoice)

            context = {
                "fname": user.fname or user.full_name or "User",
                "email": user.email,
                "showInvoice": True,
                "invoiceNumber": invoice.invoice_number,
                "invoiceDate": invoice.issued_at.strftime("%d %B %Y"),
                "invoiceType": invoice.invoice_type.replace("_", " ").title(),
                "planName": invoice.plan_name,
                "planType": invoice.plan_type,
                "subtotal": f"{invoice.subtotal:.2f}",
                "taxRate": f"{invoice.tax_rate * 100:.0f}%",
                "taxAmount": f"{invoice.tax_amount:.2f}",
                "total": f"{invoice.total:.2f}",
                "currency": invoice.currency,
                "paymentId": invoice.payment_id or "—",
                "billingName": invoice.billing_name,
                "billingEmail": invoice.billing_email,
                "periodStart": (
                    invoice.period_start.strftime("%d %B %Y")
                    if invoice.period_start else "—"
                ),
                "periodEnd": (
                    invoice.period_end.strftime("%d %B %Y")
                    if invoice.period_end else "Never"
                ),
            }

            if extra_context:
                context.update(extra_context)

            await send_mail_with_attachment(
                to_email=user.email,
                subject=subject,
                template_name="email-template.html",
                context=context,
                attachment_bytes=pdf_bytes,
                attachment_filename=f"invoice-{invoice.invoice_number}.pdf",
                attachment_content_type="application/pdf",
            )

            app_logger.info(
                "Invoice email sent number=%s to=%s",
                invoice.invoice_number, user.email,
            )

        except Exception as e:
            app_logger.error(
                "Invoice email failed number=%s user=%s: %s",
                invoice.invoice_number, user.email, e,
            )

    # ─────────────────────────────────────────
    # Read — role-aware list
    # Single method for both user and admin.
    # User  → always sees only their own invoices
    # Admin → sees all, can filter by user_id
    # ─────────────────────────────────────────

    @staticmethod
    async def get_user_invoices(
        user_id: str,
        page: int = 1,
        limit: int = 10,
        invoice_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> dict:
        """
        Fetches invoices for a specific user.
        Called by endpoint after role check resolves the correct user_id.
        Admin passes target user_id or their own.
        Regular user always passes their own id.
        """
        try:
            skip = (page - 1) * limit

            match: dict = {
                "user_id": user_id,
                "is_deleted": False,
            }

            if invoice_type:
                match["invoice_type"] = invoice_type
            if status:
                match["status"] = status

            collection = Invoice.get_pymongo_collection()

            pipeline = [
                {"$match": match},
                {"$facet": {
                    "data": [
                        {"$sort": {"issued_at": -1}},
                        {"$skip": skip},
                        {"$limit": limit},
                    ],
                    "total": [{"$count": "count"}],
                }},
            ]

            result = await collection.aggregate(pipeline).to_list(1)
            facet  = result[0] if result else {"data": [], "total": []}
            total  = facet["total"][0]["count"] if facet["total"] else 0

            return {
                "total": total,
                "page": page,
                "pages": max(1, (total + limit - 1) // limit),
                "limit": limit,
                "data": [
                    {**doc, "_id": str(doc["_id"])}
                    for doc in facet["data"]
                ],
            }

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to fetch invoices user_id=%s", user_id
            )
            raise AppException("Failed to fetch invoices", status_code=500)

    # ─────────────────────────────────────────
    # Read — admin all invoices (no user filter)
    # Called when admin wants ALL invoices across
    # every user — no user_id filter applied
    # ─────────────────────────────────────────

    @staticmethod
    async def get_all_invoices(
        page: int = 1,
        limit: int = 10,
        user_id: Optional[str] = None,
        invoice_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> dict:
        """
        Admin-only: fetches invoices across all users.
        Optionally filter by user_id, invoice_type, status.
        """
        try:
            skip  = (page - 1) * limit
            match: dict = {"is_deleted": False}

            if user_id:
                match["user_id"] = user_id
            if invoice_type:
                match["invoice_type"] = invoice_type
            if status:
                match["status"] = status

            collection = Invoice.get_pymongo_collection()

            pipeline = [
                {"$match": match},
                {"$facet": {
                    "data": [
                        {"$sort": {"issued_at": -1}},
                        {"$skip": skip},
                        {"$limit": limit},
                    ],
                    "total": [{"$count": "count"}],
                }},
            ]

            result = await collection.aggregate(pipeline).to_list(1)
            facet  = result[0] if result else {"data": [], "total": []}
            total  = facet["total"][0]["count"] if facet["total"] else 0

            return {
                "total": total,
                "page": page,
                "pages": max(1, (total + limit - 1) // limit),
                "limit": limit,
                "data": [
                    {**doc, "_id": str(doc["_id"])}
                    for doc in facet["data"]
                ],
            }

        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to fetch all invoices")
            raise AppException("Failed to fetch invoices", status_code=500)

    # ─────────────────────────────────────────
    # Read — single invoice
    # ─────────────────────────────────────────

    @staticmethod
    async def get_invoice_by_id(
        invoice_id: str,
        user_id: str,
    ) -> Invoice:
        """
        Fetches a single invoice.
        Enforces ownership — user can only fetch their own.
        Admin bypasses this by fetching Invoice directly in the endpoint.
        """
        try:
            from bson import ObjectId
            if not ObjectId.is_valid(invoice_id):
                raise ValidationException("Invalid invoice id")

            invoice = await Invoice.get(invoice_id)
            if not invoice or invoice.is_deleted:
                raise NotFoundException("Invoice not found")

            if invoice.user_id != user_id:
                raise ForbiddenException("Not allowed")

            return invoice

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to fetch invoice id=%s", invoice_id
            )
            raise AppException("Failed to fetch invoice", status_code=500)

    # ─────────────────────────────────────────
    # Void — admin only
    # ─────────────────────────────────────────

    @staticmethod
    async def void_invoice(
        invoice_id: str,
        admin_id: str,
    ) -> Invoice:
        """
        Marks invoice as VOID.
        Used when a charge was made in error or a refund was issued.
        Only admin can void — never auto-voided by system.
        """
        try:
            from bson import ObjectId
            if not ObjectId.is_valid(invoice_id):
                raise ValidationException("Invalid invoice id")

            invoice = await Invoice.get(invoice_id)
            if not invoice or invoice.is_deleted:
                raise NotFoundException("Invoice not found")

            if invoice.status == InvoiceStatus.VOID:
                raise ValidationException("Invoice is already void")

            invoice.status     = InvoiceStatus.VOID
            invoice.updated_by = admin_id
            await invoice.save()

            app_logger.info(
                "Invoice voided number=%s by admin=%s",
                invoice.invoice_number, admin_id,
            )

            return invoice

        except AppException:
            raise
        except Exception:
            app_logger.exception(
                "Failed to void invoice id=%s", invoice_id
            )
            raise AppException("Failed to void invoice", status_code=500)