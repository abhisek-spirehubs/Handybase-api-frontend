from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from app.schemas.financial_report import EarningItem, FinancialSummarySchema
from app.utils.logger import app_logger
from app.models.booking import Booking, BookingStatus, PaymentStatus


def _to_utc_datetime(d: date) -> datetime:
    return datetime.combine(d, datetime.min.time()).replace(tzinfo=timezone.utc)


def _period_dates(
    period: str,
    date_from: Optional[date],
    date_to: Optional[date],
) -> tuple[date, date]:
    today = date.today()
    if period == "week":
        return today - timedelta(days=6), today
    elif period == "month":
        return today - timedelta(days=29), today
    elif period == "quarter":
        return today - timedelta(days=89), today
    elif period == "custom":
        if not date_from or not date_to:
            raise ValueError("date_from and date_to are required for custom period")
        if date_from > date_to:
            raise ValueError("date_from must be before date_to")
        if (date_to - date_from).days > 365:
            raise ValueError("Custom range cannot exceed 365 days")
        return date_from, date_to
    else:
        return today - timedelta(days=29), today


# ── Core computation ──────────────────────────────────────────────────────────

async def compute_financial_summary(
    provider_id: str,
    period: str = "month",
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> FinancialSummarySchema:
    start, end = _period_dates(period, date_from, date_to)
    start_dt   = _to_utc_datetime(start)
    end_dt     = _to_utc_datetime(end) + timedelta(days=1)

    bookings = await Booking.find(
        Booking.provider_id == provider_id,
        Booking.is_deleted == False,
        Booking.booking_status == BookingStatus.COMPLETED,
        Booking.payment_status == PaymentStatus.PAID,
        Booking.completed_at >= start_dt,
        Booking.completed_at < end_dt,
    ).sort("completed_at").to_list()

    total_earnings  = round(sum(b.total_amount for b in bookings), 2)
    total_tax       = round(sum(b.tax for b in bookings), 2)
    total_completed = len(bookings)
    avg_earning     = round(total_earnings / total_completed, 2) if total_completed else 0.0

    earnings = [
        EarningItem(
            booking_id=str(b.id),
            service_id=str(b.service_id),
            client_id=str(b.client_id),
            booking_date=b.booking_date,
            completed_at=b.completed_at,
            price=b.price,
            tax=b.tax,
            total_amount=b.total_amount,
        )
        for b in bookings
    ]

    return FinancialSummarySchema(
        provider_id=provider_id,
        period_from=start,
        period_to=end,
        total_earnings=total_earnings,
        total_jobs_completed=total_completed,
        total_tax_collected=total_tax,
        avg_earning_per_job=avg_earning,
        earnings=earnings,
    )


# ── PDF report generation ─────────────────────────────────────────────────────

async def generate_financial_report_pdf(
    provider_id: str,
    provider_name: str,
    period: str = "month",
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table,
            TableStyle, HRFlowable, KeepTogether,
        )
        from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
        import io
    except ImportError:
        raise RuntimeError(
            "reportlab is required for PDF generation. "
            "Add 'reportlab' to requirements.txt."
        )

    summary = await compute_financial_summary(
        provider_id=provider_id,
        period=period,
        date_from=date_from,
        date_to=date_to,
    )

    # ── Colour palette ────────────────────────────────────────────────────
    DARK    = colors.HexColor("#1A1A2E")   # header / title bg
    ACCENT  = colors.HexColor("#16213E")   # section heading bg
    MUTED   = colors.HexColor("#0F3460")   # sub-heading bg
    LIGHT   = colors.HexColor("#E8F4FD")   # alt row fill
    WHITE   = colors.white
    GREY    = colors.HexColor("#6B7280")
    GREEN   = colors.HexColor("#059669")
    RED     = colors.HexColor("#DC2626")
    BORDER  = colors.HexColor("#D1D5DB")

    PAGE_W  = A4[0] - 4 * cm   # usable width

    buffer  = io.BytesIO()
    doc     = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles   = getSampleStyleSheet()
    elements = []

    # ── Styles ────────────────────────────────────────────────────────────
    def style(name, **kw):
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    S_TITLE     = style("s_title",   fontSize=22, textColor=WHITE,
                         fontName="Helvetica-Bold", leading=28)
    S_SUB       = style("s_sub",     fontSize=10, textColor=colors.HexColor("#A0AEC0"),
                         fontName="Helvetica", leading=14)
    S_LABEL     = style("s_label",   fontSize=9,  textColor=GREY,
                         fontName="Helvetica")
    S_VALUE     = style("s_value",   fontSize=14, textColor=DARK,
                         fontName="Helvetica-Bold", leading=18)
    S_SECTION   = style("s_section", fontSize=10, textColor=WHITE,
                         fontName="Helvetica-Bold")
    S_BODY      = style("s_body",    fontSize=9,  textColor=DARK,
                         fontName="Helvetica")
    S_BODY_R    = style("s_body_r",  fontSize=9,  textColor=DARK,
                         fontName="Helvetica", alignment=TA_RIGHT)
    S_BODY_BOLD = style("s_body_b",  fontSize=9,  textColor=DARK,
                         fontName="Helvetica-Bold")
    S_FOOTER    = style("s_footer",  fontSize=8,  textColor=GREY,
                         fontName="Helvetica", alignment=TA_CENTER)
    S_TOTAL_LBL = style("s_tot_l",   fontSize=10, textColor=WHITE,
                         fontName="Helvetica-Bold")
    S_TOTAL_VAL = style("s_tot_v",   fontSize=10, textColor=WHITE,
                         fontName="Helvetica-Bold", alignment=TA_RIGHT)

    INR = "\u20b9"

    # ── Header banner ─────────────────────────────────────────────────────
    header_data = [[
        Paragraph("HandyBase", S_TITLE),
        Paragraph(
            f"Financial Report<br/>"
            f"<font size='10' color='#A0AEC0'>"
            f"{summary.period_from.strftime('%d %b %Y')} &ndash; "
            f"{summary.period_to.strftime('%d %b %Y')}"
            f"</font>",
            style("hdr_r", fontSize=22, textColor=WHITE,
                  fontName="Helvetica-Bold", alignment=TA_RIGHT, leading=28),
        ),
    ]]
    header_table = Table(header_data, colWidths=[PAGE_W / 2, PAGE_W / 2])
    header_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), DARK),
        ("TOPPADDING",   (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 18),
        ("LEFTPADDING",  (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(header_table)

    # Provider + period meta row
    meta_data = [[
        Paragraph(
            f"Provider: <b>{provider_name}</b>",
            style("meta_l", fontSize=9, textColor=GREY, fontName="Helvetica"),
        ),
        Paragraph(
            f"Generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
            style("meta_r", fontSize=9, textColor=GREY,
                  fontName="Helvetica", alignment=TA_RIGHT),
        ),
    ]]
    meta_table = Table(meta_data, colWidths=[PAGE_W / 2, PAGE_W / 2])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
        ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 0.5 * cm))

    # ── KPI cards (2×2 grid) ──────────────────────────────────────────────
    # ── KPI cards (2×2 grid) ──────────────────────────────────────────────



# ── KPI cards (2×2 grid) ──────────────────────────────────────────────

    def kpi_cell(label: str, value: str, color=DARK) -> list:
        return [
            Paragraph(label, S_LABEL),
            Paragraph(value, style(
                f"kpi_{label}", fontSize=16, textColor=color,
                fontName="Helvetica-Bold", leading=20,
            )),
        ]

    net_earnings = round(summary.total_earnings - summary.total_tax_collected, 2)

    kpi_data = [
        [
            Table([kpi_cell("Total Earnings", f"{INR} {summary.total_earnings:,.2f}", GREEN)]),
            Table([kpi_cell("Jobs Completed", str(summary.total_jobs_completed))]),
            Table([kpi_cell("Tax Collected",  f"{INR} {summary.total_tax_collected:,.2f}", RED)]),
            Table([kpi_cell("Avg / Job",      f"{INR} {summary.avg_earning_per_job:,.2f}")]),
        ]
    ]

    # ✅ FIX: correct width (no subtraction)
    kpi_table = Table(
        kpi_data,
        colWidths=[PAGE_W / 4] * 4,
    )

    kpi_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), WHITE),
        ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, BORDER),

        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),

        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))

    elements.append(kpi_table)
    elements.append(Spacer(1, 0.5 * cm))



    # ── Income statement style summary ────────────────────────────────────
    section_header = Table(
        [[Paragraph("Income Statement", S_SECTION)]],
        colWidths=[PAGE_W],
    )
    section_header.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), ACCENT),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
    ]))
    elements.append(section_header)

    def stmt_row(label, value, bold=False, bg=WHITE, text_color=DARK):
        lbl_style = style(
            f"stmt_{label}", fontSize=9,
            fontName="Helvetica-Bold" if bold else "Helvetica",
            textColor=text_color,
        )
        val_style = style(
            f"stmtv_{label}", fontSize=9,
            fontName="Helvetica-Bold" if bold else "Helvetica",
            textColor=text_color, alignment=TA_RIGHT,
        )
        return [Paragraph(label, lbl_style), Paragraph(value, val_style)]

    stmt_data = [
        stmt_row("Revenue",                    ""),
        stmt_row(f"  Gross Earnings ({summary.total_jobs_completed} jobs)",
                 f"{INR} {summary.total_earnings:,.2f}"),
        stmt_row("  Less: Tax / GST Collected",
                 f"({INR} {summary.total_tax_collected:,.2f})", text_color=RED),
        stmt_row("Net Earnings",
                 f"{INR} {net_earnings:,.2f}", bold=True, bg=LIGHT),
        stmt_row("",                            ""),
        stmt_row("Per-Job Metrics",             ""),
        stmt_row("  Average Earning / Job",
                 f"{INR} {summary.avg_earning_per_job:,.2f}"),
        stmt_row("  Average Tax / Job",
                 f"{INR} {round(summary.total_tax_collected / summary.total_jobs_completed, 2) if summary.total_jobs_completed else 0:,.2f}"),
    ]

    stmt_table = Table(stmt_data, colWidths=[PAGE_W * 0.65, PAGE_W * 0.35])
    stmt_style = [
        ("BACKGROUND",    (0, 0), (-1, -1), WHITE),
        ("BACKGROUND",    (0, 3), (-1, 3),  LIGHT),
        ("FONTNAME",      (0, 3), (-1, 3),  "Helvetica-Bold"),
        ("LINEBELOW",     (0, 2), (-1, 2),  0.5, BORDER),
        ("LINEABOVE",     (0, 3), (-1, 3),  0.5, BORDER),
        ("LINEBELOW",     (0, 3), (-1, 3),  1,   ACCENT),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
    ]
    stmt_table.setStyle(TableStyle(stmt_style))
    elements.append(stmt_table)
    elements.append(Spacer(1, 0.5 * cm))

    # ── Earnings breakdown table ──────────────────────────────────────────
    breakdown_header = Table(
        [[Paragraph("Earnings Breakdown", S_SECTION)]],
        colWidths=[PAGE_W],
    )
    breakdown_header.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), MUTED),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
    ]))
    elements.append(breakdown_header)

    if summary.earnings:
        # Column widths: # | Booking | Service Date | Completed | Price | Tax | Total
        COL_W = [
            0.6 * cm,    # #
            4.0 * cm,    # Booking ID
            2.8 * cm,    # Service Date
            2.8 * cm,    # Completed
            2.4 * cm,    # Price
            2.0 * cm,    # Tax
            2.8 * cm,    # Total
        ]

        def hdr(text):
            return Paragraph(text, style(
                f"th_{text}", fontSize=8, textColor=WHITE,
                fontName="Helvetica-Bold",
            ))

        def cell(text, right=False, bold=False):
            return Paragraph(text, style(
                f"td_{text}", fontSize=8, textColor=DARK,
                fontName="Helvetica-Bold" if bold else "Helvetica",
                alignment=TA_RIGHT if right else TA_LEFT,
            ))

        rows = [[
            hdr("#"), hdr("Booking ID"), hdr("Service Date"),
            hdr("Completed On"), hdr("Price"), hdr("Tax"), hdr("Total"),
        ]]

        for i, item in enumerate(summary.earnings, 1):
            completed_str = (
                item.completed_at.strftime("%d %b %Y")
                if item.completed_at else "—"
            )
            rows.append([
                cell(str(i)),
                cell(str(item.booking_id)[-10:]),
                cell(item.booking_date.strftime("%d %b %Y")),
                cell(completed_str),
                cell(f"{INR} {item.price:,.2f}", right=True),
                cell(f"{INR} {item.tax:,.2f}",   right=True),
                cell(f"{INR} {item.total_amount:,.2f}", right=True, bold=True),
            ])

        # Totals row
        rows.append([
            Paragraph("", S_BODY),
            Paragraph("", S_BODY),
            Paragraph("", S_BODY),
            Paragraph("Total", style(
                "tot_lbl", fontSize=9, textColor=WHITE,
                fontName="Helvetica-Bold",
            )),
            Paragraph(
                f"{INR} {sum(e.price for e in summary.earnings):,.2f}",
                style("tot_p", fontSize=9, textColor=WHITE,
                      fontName="Helvetica-Bold", alignment=TA_RIGHT),
            ),
            Paragraph(
                f"{INR} {summary.total_tax_collected:,.2f}",
                style("tot_t", fontSize=9, textColor=WHITE,
                      fontName="Helvetica-Bold", alignment=TA_RIGHT),
            ),
            Paragraph(
                f"{INR} {summary.total_earnings:,.2f}",
                style("tot_v", fontSize=9, textColor=WHITE,
                      fontName="Helvetica-Bold", alignment=TA_RIGHT),
            ),
        ])

        n = len(rows)
        bd_table = Table(rows, colWidths=COL_W, repeatRows=1)
        bd_style = [
            # Header row
            ("BACKGROUND",    (0, 0), (-1, 0),     DARK),
            ("TEXTCOLOR",     (0, 0), (-1, 0),     WHITE),
            ("TOPPADDING",    (0, 0), (-1, 0),     8),
            ("BOTTOMPADDING", (0, 0), (-1, 0),     8),
            # Alternating rows
            ("ROWBACKGROUNDS",(0, 1), (-1, n - 2), [WHITE, LIGHT]),
            # Totals row
            ("BACKGROUND",    (0, n - 1), (-1, n - 1), ACCENT),
            ("LINEABOVE",     (0, n - 1), (-1, n - 1), 1, DARK),
            # All rows
            ("GRID",          (0, 0), (-1, -1),    0.3, BORDER),
            ("TOPPADDING",    (0, 1), (-1, -1),    5),
            ("BOTTOMPADDING", (0, 1), (-1, -1),    5),
            ("LEFTPADDING",   (0, 0), (-1, -1),    6),
            ("RIGHTPADDING",  (0, 0), (-1, -1),    6),
            ("VALIGN",        (0, 0), (-1, -1),    "MIDDLE"),
        ]
        bd_table.setStyle(TableStyle(bd_style))
        elements.append(bd_table)

    else:
        no_data = Table(
            [[Paragraph("No completed & paid jobs found in this period.", S_BODY)]],
            colWidths=[PAGE_W],
        )
        no_data.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#FEF3C7")),
            ("TOPPADDING",    (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("LEFTPADDING",   (0, 0), (-1, -1), 12),
            ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#F59E0B")),
        ]))
        elements.append(no_data)

    # ── Footer ────────────────────────────────────────────────────────────
    elements.append(Spacer(1, 0.8 * cm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    elements.append(Spacer(1, 0.2 * cm))
    elements.append(Paragraph(
        f"This report is auto-generated by HandyBase  |  "
        f"Period: {summary.period_from.strftime('%d %b %Y')} – "
        f"{summary.period_to.strftime('%d %b %Y')}  |  "
        f"Provider ID: {provider_id[-8:]}",
        S_FOOTER,
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer.read()