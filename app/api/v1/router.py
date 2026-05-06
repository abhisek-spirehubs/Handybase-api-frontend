from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    health,
    service,
    category,
    client,
    provider,
    booking,
    notification,
    chat_message,
    review,
)
from app.api.v1.endpoints.plan import router as plan_router
from app.api.v1.endpoints.subscription import router as subscription_router
from app.api.v1.endpoints.invoice import router as invoice_router
from app.api.v1.endpoints.availability import router as availability_router
from app.api.v1.endpoints.dashboard import router as dashboard_router
from app.api.v1.endpoints import analytics
from app.api.v1.endpoints import financial_report
from app.api.v1.endpoints.video_portfolio import router as video_portfolio_router
from app.api.v1.endpoints.client_review import router as client_review_router
from app.api.v1.endpoints.client_features import router as  client_features_router
from app.api.v1.endpoints.job_request import router as job_request_router
from app.api.v1.endpoints.document_exchange import router as document_exchange_router
from app.api.v1.endpoints.support_ticket import router as support_ticket_router
from app.api.v1.endpoints.announcement import router as announcement_router
from app.api.v1.endpoints import fcm


api_router = APIRouter()

# ── Health ────────────────────────────────────────────────────────────────────
api_router.include_router(
    health.router,
    prefix="/health",
    tags=["Health"],
)

# ── Auth ──────────────────────────────────────────────────────────────────────
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Auth"],
)

# ── Clients ───────────────────────────────────────────────────────────────────
api_router.include_router(
    client.router,
    prefix="/clients",
    tags=["Clients"],
)

# ── Providers ─────────────────────────────────────────────────────────────────
api_router.include_router(
    provider.router,
    prefix="/providers",
    tags=["Providers"],
)

# ── Plans ─────────────────────────────────────────────────────────────────────
api_router.include_router(
    plan_router,
    prefix="/plans",
    tags=["Plans"],
)

# ── Subscriptions ─────────────────────────────────────────────────────────────
api_router.include_router(
    subscription_router,
    prefix="/subscriptions",
    tags=["Subscriptions"],
)

# ── Categories ────────────────────────────────────────────────────────────────
api_router.include_router(
    category.router,
    prefix="/categories",
    tags=["Categories"],
)

# ── Services ──────────────────────────────────────────────────────────────────
api_router.include_router(
    service.router,
    prefix="/services",
    tags=["Services"],
)

# ── Availability ──────────────────────────────────────────────────────────────
api_router.include_router(
    availability_router,
    prefix="/availability",
    tags=["Availability"],
)

# ── Bookings ──────────────────────────────────────────────────────────────────
api_router.include_router(
    booking.router,
    prefix="/bookings",
    tags=["Bookings"],
)

# ── Chats ─────────────────────────────────────────────────────────────────────
api_router.include_router(
    chat_message.router,
    prefix="/chats",
    tags=["Chats"],
)

# ── Reviews (client → provider) ───────────────────────────────────────────────
api_router.include_router(
    review.router,
    prefix="/reviews",
    tags=["Reviews"],
)

# ── Notifications ─────────────────────────────────────────────────────────────
api_router.include_router(
    notification.router,
    prefix="/notifications",
    tags=["Notifications"],
)

# ── Invoices ──────────────────────────────────────────────────────────────────
api_router.include_router(
    invoice_router,
    prefix="/invoices",
    tags=["Invoices"],
)

# ── Admin ─────────────────────────────────────────────────────────────────────
api_router.include_router(
    dashboard_router,
    prefix="/admin",
    tags=["Admin"],
)

# ── Advanced Provider Tools — Analytics (Tier 3) ──────────────────────────────
api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["Advanced Provider Tools"],
)

# ── Advanced Provider Tools — Financial Reports (Tier 3) ──────────────────────
api_router.include_router(
    financial_report.router,
    prefix="/financial-report",
    tags=["Financial Reporting"],
)

api_router.include_router(
    video_portfolio_router,
    prefix="/portfolio-videos",
    tags=["Video Portfolio Uploads"],
)


# ── Advanced Provider Tools — Video Portfolio (Tier 3) ────────────────────────
api_router.include_router(
    client_review_router,
    prefix="/client-review",
    tags=["Customer Rating by Providers"],
)

api_router.include_router(client_features_router, tags=["Quotation & Price comparison(Client features)"])

api_router.include_router(job_request_router, prefix="/job")

api_router.include_router(document_exchange_router, tags=["Secure Document Exchange"])

api_router.include_router(
    support_ticket_router,
    prefix="/support",
    tags=["Support Ticket"],
)

api_router.include_router(
    announcement_router,
    prefix="/announcements",
    tags=["Announcements"],
)

api_router.include_router(fcm.router, prefix="/fcm", tags=["fcm"])