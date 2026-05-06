import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT


# ── Brand colors ──────────────────────────────────────────────────────────────
DARK        = colors.HexColor("#1a1a1a")
GREY        = colors.HexColor("#555555")
LIGHT_GREY  = colors.HexColor("#888888")
LINE_COLOR  = colors.HexColor("#cccccc")


def _status_color(status: str) -> colors.HexColor:
    """Returns color based on invoice status."""
    return {
        "paid":   colors.HexColor("#2e7d32"),  # green
        "unpaid": colors.HexColor("#e65100"),  # orange
        "void":   colors.HexColor("#b71c1c"),  # red
    }.get(status.lower(), colors.HexColor("#555555"))


def generate_invoice_pdf(invoice) -> bytes:
    """
    Generates a professional PDF invoice matching Handybase design.
    Accepts an Invoice model instance.
    Returns raw bytes — used for email attachment or HTTP download response.

    Fixes applied:
    - Status badge moved to meta row — no longer overlaps "Invoice" title
    - Status color is dynamic — green/orange/red based on value
    - Invoice title is clean — just the word "Invoice" on the right
    """
    buffer   = io.BytesIO()
    page_w, _ = A4
    margin   = 18 * mm
    usable_w = page_w - 2 * margin

    styles = getSampleStyleSheet()

    def s(name, **kwargs):
        return ParagraphStyle(name, parent=styles["Normal"], **kwargs)

    # ── Resolve status ────────────────────────────────────────────────────────
    status_str   = str(invoice.status).lower().replace("invoicestatus.", "")
    status_label = status_str.upper()
    status_color = _status_color(status_str)

    # ── Styles ────────────────────────────────────────────────────────────────
    s_company  = s("company",  fontSize=22, fontName="Helvetica-Bold", textColor=DARK)
    s_inv_lbl  = s("inv_lbl",  fontSize=22, fontName="Helvetica",      textColor=LIGHT_GREY, alignment=TA_RIGHT)
    s_status   = s("status",   fontSize=10, fontName="Helvetica-Bold", textColor=status_color, alignment=TA_RIGHT)
    s_meta     = s("meta",     fontSize=9,  fontName="Helvetica",      textColor=DARK,        leading=14)
    s_label    = s("lbl",      fontSize=8,  fontName="Helvetica-Bold", textColor=LIGHT_GREY,  leading=14)
    s_val      = s("val",      fontSize=9,  fontName="Helvetica",      textColor=DARK,        leading=14)
    s_small    = s("small",    fontSize=8,  fontName="Helvetica",      textColor=LIGHT_GREY,  leading=13)
    s_small_c  = s("small_c",  fontSize=8,  fontName="Helvetica",      textColor=LIGHT_GREY,  leading=13, alignment=TA_CENTER)
    s_th       = s("th",       fontSize=8,  fontName="Helvetica-Bold", textColor=DARK)
    s_th_r     = s("th_r",     fontSize=8,  fontName="Helvetica-Bold", textColor=DARK,        alignment=TA_RIGHT)
    s_body     = s("body",     fontSize=9,  fontName="Helvetica",      textColor=DARK,        leading=15)
    s_body_sm  = s("body_sm",  fontSize=7,  fontName="Helvetica",      textColor=LIGHT_GREY,  leading=12)
    s_val_r    = s("val_r",    fontSize=9,  fontName="Helvetica",      textColor=DARK,        leading=14, alignment=TA_RIGHT)
    s_total_r  = s("tot_r",    fontSize=10, fontName="Helvetica-Bold", textColor=DARK,        alignment=TA_RIGHT)

    elements = []

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=margin,
        leftMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
    )

    def divider():
        t = Table([[""]], colWidths=[usable_w], rowHeights=[0.4 * mm])
        t.setStyle(TableStyle([
            ("LINEBELOW",     (0, 0), (-1, -1), 0.5, LINE_COLOR),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        return t

    # ══════════════════════════════════════════════════════════════════════════
    # HEADER — "Handybase" left, "Invoice" right (no status here)
    # ══════════════════════════════════════════════════════════════════════════
    header = Table(
        [[
            Paragraph("Handybase", s_company),
            Paragraph("Invoice",   s_inv_lbl),
        ]],
        colWidths=[usable_w * 0.55, usable_w * 0.45],
    )
    header.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(header)
    elements.append(Spacer(1, 3 * mm))
    elements.append(divider())
    elements.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════════════════════════
    # META ROW — Invoice #  |  Issue Date  |  Due Date  |  STATUS (badge)
    # Status is here — clean, right-aligned, colored, no overlap
    # ══════════════════════════════════════════════════════════════════════════
    issue_date = invoice.issued_at.strftime("%Y-%m-%d")
    due_date   = (
        invoice.period_end.strftime("%Y-%m-%d")
        if invoice.period_end else issue_date
    )

    meta = Table(
        [[
            Paragraph(f"Invoice #: {invoice.invoice_number}", s_meta),
            Paragraph(f"Issue Date: {issue_date}",            s_meta),
            Paragraph(f"Due Date: {due_date}",                s_meta),
            Paragraph(status_label,                           s_status),
        ]],
        colWidths=[
            usable_w * 0.34,
            usable_w * 0.24,
            usable_w * 0.24,
            usable_w * 0.18,
        ],
    )
    meta.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(meta)
    elements.append(Spacer(1, 6 * mm))
    elements.append(divider())
    elements.append(Spacer(1, 6 * mm))

    # ══════════════════════════════════════════════════════════════════════════
    # ISSUED BY / BILLED TO
    # ══════════════════════════════════════════════════════════════════════════
    def info_block(heading, name, email):
        return Table(
            [[Paragraph(heading, s_label)],
             [Paragraph(name,    s_val)],
             [Paragraph(email,   s_small)]],
            colWidths=[usable_w * 0.45],
            style=TableStyle([
                ("TOPPADDING",    (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ]),
        )

    parties = Table(
        [[
            info_block("ISSUED BY", "Handybase", "support@handybase.com"),
            info_block(
                "BILLED TO",
                invoice.billing_name  or "—",
                invoice.billing_email or "—",
            ),
        ]],
        colWidths=[usable_w * 0.5, usable_w * 0.5],
    )
    parties.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    elements.append(parties)
    elements.append(Spacer(1, 8 * mm))

    # ══════════════════════════════════════════════════════════════════════════
    # LINE ITEMS
    # ══════════════════════════════════════════════════════════════════════════
    col_desc = usable_w * 0.55
    col_qty  = usable_w * 0.20
    col_amt  = usable_w * 0.25

    period_str = "—"
    if invoice.period_start and invoice.period_end:
        period_str = (
            f"{invoice.period_start.strftime('%Y-%m-%d')} - "
            f"{invoice.period_end.strftime('%Y-%m-%d')}"
        )
    elif invoice.period_start:
        period_str = f"From {invoice.period_start.strftime('%Y-%m-%d')}"

    items_data = [
        # Header row
        [
            Paragraph("DESCRIPTION", s_th),
            Paragraph("QTY",         s_th_r),
            Paragraph("AMOUNT",      s_th_r),
        ],
        # Item row
        [
            Table(
                [[Paragraph(invoice.plan_name, s_body)],
                 [Paragraph(f"Period: {period_str}", s_body_sm)]],
                colWidths=[col_desc],
                style=TableStyle([
                    ("TOPPADDING",    (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                ]),
            ),
            Paragraph("1", s_val_r),
            Paragraph(f"{invoice.currency} {invoice.subtotal:.2f}", s_val_r),
        ],
    ]

    items_table = Table(
        items_data,
        colWidths=[col_desc, col_qty, col_amt],
    )
    items_table.setStyle(TableStyle([
        ("LINEBELOW",     (0, 0), (-1, 0),  0.5, LINE_COLOR),
        ("TOPPADDING",    (0, 0), (-1, 0),  6),
        ("BOTTOMPADDING", (0, 0), (-1, 0),  6),
        ("TOPPADDING",    (0, 1), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 8),
        ("LINEBELOW",     (0, -1), (-1, -1), 0.5, LINE_COLOR),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════════════════════════
    # TOTALS
    # ══════════════════════════════════════════════════════════════════════════
    spacer_w = usable_w * 0.60
    label_w  = usable_w * 0.22
    amt_w    = usable_w * 0.18

    totals_rows = [[
        "",
        Paragraph("Subtotal", s_val_r),
        Paragraph(f"{invoice.currency} {invoice.subtotal:.2f}", s_val_r),
    ]]

    if invoice.tax_rate > 0:
        totals_rows.append([
            "",
            Paragraph(f"Tax ({invoice.tax_rate * 100:.0f}%)", s_val_r),
            Paragraph(f"{invoice.currency} {invoice.tax_amount:.2f}", s_val_r),
        ])

    totals_rows.append([
        "",
        Paragraph("Total Paid", s_total_r),
        Paragraph(f"{invoice.currency} {invoice.total:.2f}", s_total_r),
    ])

    total_row = len(totals_rows) - 1
    totals_table = Table(
        totals_rows,
        colWidths=[spacer_w, label_w, amt_w],
    )
    totals_table.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("LINEABOVE",     (1, total_row), (-1, total_row), 0.5, LINE_COLOR),
    ]))
    elements.append(totals_table)

    # ── Payment reference — only shown for real payments ──────────────────────
    if invoice.payment_id and not str(invoice.payment_id).startswith(("free_", "admin_grant_")):
        elements.append(Spacer(1, 4 * mm))
        elements.append(divider())
        elements.append(Spacer(1, 3 * mm))
        elements.append(Paragraph(
            f"Payment Reference: {invoice.payment_id}",
            s_small,
        ))

    # ══════════════════════════════════════════════════════════════════════════
    # FOOTER
    # ══════════════════════════════════════════════════════════════════════════
    elements.append(Spacer(1, 10 * mm))
    elements.append(divider())
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(
        "Thank you for your business — <b>Handybase Team</b> | "
        "Contact us at <b>support@handybase.com</b> within 30 days for assistance.",
        s_small_c,
    ))

    doc.build(elements)
    return buffer.getvalue()