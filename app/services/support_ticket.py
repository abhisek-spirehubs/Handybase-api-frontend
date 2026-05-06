from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import BackgroundTasks

from app.models.support_ticket import SupportTicket, TicketCategory, TicketReply, TicketStatus
from app.models.user import User
from app.schemas.support_ticket import TicketCreate, TicketReplySchema
from app.services.notification_orchestrator import NotificationOrchestrator  # <-- changed
from app.utils.email import send_mail
from app.utils.logger import app_logger
from app.core.exceptions import (
    AppException, ForbiddenException, NotFoundException, ValidationException,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SupportService:

    @staticmethod
    async def create_ticket(user_id: str, data: TicketCreate) -> SupportTicket:
        try:
            ticket = SupportTicket(
                user_id=user_id,
                subject=data.subject,
                message=data.message,
                category=data.category,
                created_by=user_id,
            )
            await ticket.insert()
            app_logger.info("Ticket created ticket_id=%s user_id=%s", str(ticket.id), user_id)
            return ticket
        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to create ticket user_id=%s", user_id)
            raise AppException("Failed to create support ticket", status_code=500)

    @staticmethod
    async def get_my_tickets(
        user_id: str,
        page: int,
        limit: int,
        status: Optional[TicketStatus] = None,
    ) -> dict:
        try:
            skip = (page - 1) * limit
            query: dict = {"user_id": user_id, "is_deleted": False}
            if status:
                query["status"] = status

            total = await SupportTicket.find(query).count()
            tickets = await SupportTicket.find(query) \
                .sort("-created_at") \
                .skip(skip) \
                .limit(limit) \
                .to_list()

            return {
                "success": True,
                "message": "Your tickets fetched successfully",
                "total": total,
                "data": tickets,
            }
        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to fetch user tickets user_id=%s", user_id)
            raise AppException("Failed to fetch tickets", status_code=500)

    @staticmethod
    async def get_all_tickets(
        page: int,
        limit: int,
        status: Optional[TicketStatus] = None,
        category: Optional[TicketCategory] = None,
    ) -> dict:
        try:
            skip = (page - 1) * limit
            query: dict = {"is_deleted": False}
            if status:
                query["status"] = status
            if category:
                query["category"] = category

            total = await SupportTicket.find(query).count()
            tickets = await SupportTicket.find(query) \
                .sort("-created_at") \
                .skip(skip) \
                .limit(limit) \
                .to_list()

            return {
                "success": True,
                "message": "All tickets fetched successfully",
                "total": total,
                "data": tickets,
            }
        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to fetch all tickets")
            raise AppException("Failed to fetch tickets", status_code=500)

    @staticmethod
    async def get_ticket(ticket_id: str, caller_id: str, is_admin: bool) -> SupportTicket:
        try:
            if not ObjectId.is_valid(ticket_id):
                raise ValidationException("Invalid ticket id")
            ticket = await SupportTicket.get(ticket_id)
            if not ticket or ticket.is_deleted:
                raise NotFoundException("Ticket not found")
            if not is_admin and ticket.user_id != caller_id:
                raise ForbiddenException("Not allowed to view this ticket")
            return ticket
        except AppException:
            raise
        except Exception:
            app_logger.exception("Failed to fetch ticket ticket_id=%s", ticket_id)
            raise AppException("Failed to fetch ticket", status_code=500)

    @staticmethod
    async def reply_ticket(
        ticket_id: str,
        admin: User,
        data: TicketReplySchema,
        background_tasks: BackgroundTasks,
    ) -> SupportTicket:
        try:
            if not ObjectId.is_valid(ticket_id):
                raise ValidationException("Invalid ticket id")
            ticket = await SupportTicket.get(ticket_id)
            if not ticket or ticket.is_deleted:
                raise NotFoundException("Ticket not found")
            if ticket.status == TicketStatus.CLOSED:
                raise AppException("Cannot reply to a closed ticket. Reopen it first.", status_code=400)

            reply = TicketReply(message=data.message, replied_by=str(admin.id))
            ticket.replies.append(reply)
            if data.admin_note:
                ticket.admin_note = data.admin_note
            ticket.updated_by = str(admin.id)
            await ticket.save()

            ticket_user = await User.get(ticket.user_id)

            # Use NotificationOrchestrator for both in-app and push
            background_tasks.add_task(
                NotificationOrchestrator.notify_user,
                user_id=ticket.user_id,
                title="Support Reply",
                body="Your support ticket has received a response. Check your email.",
                notification_type="TICKET_REPLY",
                background_tasks=background_tasks,  # pass through for nested tasks
                data={"ticket_id": str(ticket.id), "type": "TICKET_REPLY"},
                path=f"/support/tickets/{ticket_id}",
                send_in_app=True,
                send_push=True,
            )

            # Send email
            if ticket_user and ticket_user.email:
                background_tasks.add_task(
                    send_mail,
                    {"to": ticket_user.email, "subject": f"Re: {ticket.subject} — HandyBase Support"},
                    {
                        "fname":        ticket_user.full_name or ticket_user.fname or "User",
                        "email":        ticket_user.email,
                        "ticket_id":    str(ticket.id),
                        "subject":      ticket.subject,
                        "message":      data.message,
                        "supportReply": True,
                    },
                    "email-template.html",
                )

            app_logger.info("Ticket replied ticket_id=%s admin_id=%s", ticket_id, str(admin.id))
            return ticket
        except AppException:
            raise
        except Exception:
            app_logger.exception("Reply failed ticket_id=%s", ticket_id)
            raise AppException("Failed to send reply", status_code=500)

    @staticmethod
    async def close_ticket(
        ticket_id: str,
        admin: User,
        background_tasks: BackgroundTasks,
    ) -> SupportTicket:
        try:
            if not ObjectId.is_valid(ticket_id):
                raise ValidationException("Invalid ticket id")
            ticket = await SupportTicket.get(ticket_id)
            if not ticket or ticket.is_deleted:
                raise NotFoundException("Ticket not found")
            if ticket.status == TicketStatus.CLOSED:
                raise AppException("Ticket is already closed", status_code=400)

            ticket.status     = TicketStatus.CLOSED
            ticket.closed_at  = _utc_now()
            ticket.closed_by  = str(admin.id)
            ticket.updated_by = str(admin.id)
            await ticket.save()

            ticket_user = await User.get(ticket.user_id)

            # Use NotificationOrchestrator
            background_tasks.add_task(
                NotificationOrchestrator.notify_user,
                user_id=ticket.user_id,
                title="Support Ticket Closed",
                body="Your support ticket has been resolved and closed.",
                notification_type="TICKET_CLOSED",
                background_tasks=background_tasks,
                data={"ticket_id": str(ticket.id), "type": "TICKET_CLOSED"},
                path=f"/support/tickets/{ticket_id}",
                send_in_app=True,
                send_push=True,
            )

            # Send email
            if ticket_user and ticket_user.email:
                background_tasks.add_task(
                    send_mail,
                    {"to": ticket_user.email, "subject": f"Ticket Resolved: {ticket.subject}"},
                    {
                        "fname":        ticket_user.full_name or ticket_user.fname or "User",
                        "email":        ticket_user.email,
                        "ticket_id":    str(ticket.id),
                        "subject":      ticket.subject,
                        "ticketClosed": True,
                    },
                    "email-template.html",
                )

            app_logger.info("Ticket closed ticket_id=%s admin_id=%s", ticket_id, str(admin.id))
            return ticket
        except AppException:
            raise
        except Exception:
            app_logger.exception("Close failed ticket_id=%s", ticket_id)
            raise AppException("Failed to close ticket", status_code=500)

    @staticmethod
    async def reopen_ticket(ticket_id: str, admin: User) -> SupportTicket:
        try:
            if not ObjectId.is_valid(ticket_id):
                raise ValidationException("Invalid ticket id")
            ticket = await SupportTicket.get(ticket_id)
            if not ticket or ticket.is_deleted:
                raise NotFoundException("Ticket not found")
            if ticket.status == TicketStatus.OPEN:
                raise AppException("Ticket is already open", status_code=400)

            ticket.status     = TicketStatus.OPEN
            ticket.closed_at  = None
            ticket.closed_by  = None
            ticket.updated_by = str(admin.id)
            await ticket.save()

            # Optional: send a notification to user about reopening?
            # We can add if needed, but not required.

            app_logger.info("Ticket reopened ticket_id=%s admin_id=%s", ticket_id, str(admin.id))
            return ticket
        except AppException:
            raise
        except Exception:
            app_logger.exception("Reopen failed ticket_id=%s", ticket_id)
            raise AppException("Failed to reopen ticket", status_code=500)

    @staticmethod
    async def delete_ticket(ticket_id: str, admin: User) -> None:
        try:
            if not ObjectId.is_valid(ticket_id):
                raise ValidationException("Invalid ticket id")
            ticket = await SupportTicket.get(ticket_id)
            if not ticket or ticket.is_deleted:
                raise NotFoundException("Ticket not found")
            await ticket.soft_delete(str(admin.id))
            app_logger.info("Ticket deleted ticket_id=%s admin_id=%s", ticket_id, str(admin.id))
        except AppException:
            raise
        except Exception:
            app_logger.exception("Delete failed ticket_id=%s", ticket_id)
            raise AppException("Failed to delete ticket", status_code=500)