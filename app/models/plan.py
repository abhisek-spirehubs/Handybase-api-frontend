from enum import Enum
from pydantic import BaseModel


class PlanType(str, Enum):
    CLIENT_FREE    = "client_free"
    CLIENT_PAID    = "client_paid"
    PROVIDER_TIER1 = "provider_tier1"
    PROVIDER_TIER2 = "provider_tier2"
    PROVIDER_TIER3 = "provider_tier3"


class PlanFeatures(BaseModel):
    """
    Feature flags snapshot.
    Stored both on Plan (template) and Subscription (snapshot at purchase time).
    Snapshot means if admin changes the plan later, existing subscribers keep
    exactly what they paid for.
    """

    # ── Client features ───────────────────────────────────────────────────
    can_chat:                 bool = False
    can_book:                 bool = False
    can_compare_prices:       bool = False
    can_request_quotes:       bool = False
    can_use_advanced_filters: bool = False
    can_view_full_profiles:   bool = False
    can_leave_reviews:        bool = False
    can_exchange_documents:   bool = False

    # ── Provider features — Tier 1 ────────────────────────────────────────
    can_list_services:        bool = False

    # ── Provider features — Tier 2 ────────────────────────────────────────
    can_set_pricing:          bool = False
    can_use_calendar:         bool = False
    can_receive_payments:     bool = False
    can_use_messaging:        bool = False

    # ── Provider features — Tier 3 ────────────────────────────────────────
    can_view_analytics:       bool = False   # analytics dashboard
    can_view_reports:         bool = False   # financial reports / PDF download
    has_priority_listing:     bool = False   # priority in search results
    can_upload_videos:        bool = False   # video portfolio uploads
    can_rate_clients:         bool = False   # provider rates client after job

    # ── Limits ────────────────────────────────────────────────────────────
    max_services:             int  = 3       # -1 = unlimited
    max_portfolio_images:     int  = 4

    can_manage_bookings: bool = False
    can_view_job_history: bool = False
    can_make_payments: bool = False
    is_search_limited: bool = False


# ── Default feature sets ──────────────────────────────────────────────────────

CLIENT_FREE_FEATURES = PlanFeatures()

CLIENT_PAID_FEATURES = PlanFeatures(
    can_chat=True,
    can_book=True,
    can_compare_prices=True,
    can_request_quotes=True,
    can_use_advanced_filters=True,
    can_view_full_profiles=True,
    can_leave_reviews=True,
    can_exchange_documents=True,
)

PROVIDER_TIER1_FEATURES = PlanFeatures(
    can_list_services=True,
    max_services=3,
    max_portfolio_images=4,
)

PROVIDER_TIER2_FEATURES = PlanFeatures(
    can_list_services=True,
    can_set_pricing=True,
    can_use_calendar=True,
    can_receive_payments=True,
    can_use_messaging=True,
    can_exchange_documents=True,
    max_services=10,
    max_portfolio_images=4,
)

PROVIDER_TIER3_FEATURES = PlanFeatures(
    # All Tier 2 features included
    can_list_services=True,
    can_set_pricing=True,
    can_use_calendar=True,
    can_receive_payments=True,
    can_use_messaging=True,
    can_exchange_documents=True,
    # Tier 3 exclusive
    can_view_analytics=True,
    can_view_reports=True,
    has_priority_listing=True,
    can_upload_videos=True,
    can_rate_clients=True,
    # Limits
    max_services=-1,
    max_portfolio_images=4,
)