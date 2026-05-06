import aiosmtplib
from email.message import EmailMessage
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.core.config import settings
from pathlib import Path
from typing import Optional


# ── Template setup ────────────────────────────────────────────────────────────
template_path = Path(__file__).parent.parent / "templates"
env = Environment(
    loader=FileSystemLoader(template_path),
    autoescape=select_autoescape(["html", "xml"]),
)


def _render_template(template_name: str, context: dict) -> str:
    """Render a Jinja2 HTML template with given context."""
    template = env.get_template(template_name)
    return template.render(**context)


# ── Send plain email ──────────────────────────────────────────────────────────

async def send_mail(
    email_data: dict,
    replacements: dict,
    html_file_name: str,
) -> dict:
    """
    Send email using HTML template.

    Args:
        email_data:    {"to": "user@example.com", "subject": "..."}
        replacements:  template variables dict
        html_file_name: template file name e.g. "email-template.html"
    """
    try:
        replacements = replacements or {}

        html_content = _render_template(html_file_name, replacements)

        message = EmailMessage()
        message["From"]    = settings.SMTP_FROM
        message["To"]      = email_data["to"]
        message["Subject"] = email_data["subject"]
        message.set_content("This email requires HTML support.")
        message.add_alternative(html_content, subtype="html")

        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )

        return {"status": "sent"}

    except Exception as e:
        print("Email sending failed:", str(e))
        return {"status": "failed", "error": str(e)}


# ── Send email with PDF attachment ────────────────────────────────────────────

async def send_mail_with_attachment(
    to_email: str,
    subject: str,
    template_name: str,
    context: dict,
    attachment_bytes: bytes,
    attachment_filename: str,
    attachment_content_type: str = "application/pdf",
) -> dict:
    """
    Send email with a file attachment using same SMTP setup as send_mail.

    Args:
        to_email:                 recipient email address
        subject:                  email subject line
        template_name:            Jinja2 template file name
        context:                  template variables dict
        attachment_bytes:         raw bytes of the file to attach (e.g. PDF)
        attachment_filename:      filename shown to recipient e.g. "invoice-HB-2026-000001.pdf"
        attachment_content_type:  MIME type of attachment (default: application/pdf)

    Uses EmailMessage (stdlib) — same as send_mail, no MIMEMultipart needed.
    aiosmtplib works natively with EmailMessage.
    """
    try:
        context = context or {}

        html_content = _render_template(template_name, context)

        message = EmailMessage()
        message["From"]    = settings.SMTP_FROM
        message["To"]      = to_email
        message["Subject"] = subject

        # Plain text fallback
        message.set_content("This email requires HTML support.")

        # HTML body
        message.add_alternative(html_content, subtype="html")

        # PDF attachment — add_attachment handles base64 encoding automatically
        message.add_attachment(
            attachment_bytes,
            maintype=attachment_content_type.split("/")[0],   # "application"
            subtype=attachment_content_type.split("/")[1],    # "pdf"
            filename=attachment_filename,
        )

        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )

        return {"status": "sent"}

    except Exception as e:
        print("Email with attachment sending failed:", str(e))
        return {"status": "failed", "error": str(e)}