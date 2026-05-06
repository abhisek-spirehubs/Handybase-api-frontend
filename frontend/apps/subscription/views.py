from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View

from apps.core.api_client import APIError, get_api_client
from apps.core.mixins import APIViewMixin


def _current_user(request):
    return request.session.get("user", {}) or {}


def _user_type(user):
    return (user.get("user_type") or "client").lower()


def _user_id(user):
    return user.get("_id") or user.get("id") or "user"


def _normalize_plan(plan):
    if "_id" in plan and "id" not in plan:
        plan["id"] = str(plan["_id"])

    features = plan.get("features") or {}
    if isinstance(features, dict):
        plan["display_features"] = [
            key.replace("can_", "").replace("_", " ").title()
            for key, value in features.items()
            if value is True
        ]
    elif isinstance(features, list):
        plan["display_features"] = features
    else:
        plan["display_features"] = []

    price = plan.get("price") or plan.get("monthly_price") or plan.get("amount") or 0
    plan["display_price"] = price
    plan["display_name"] = plan.get("name") or plan.get("plan_name") or plan.get("title") or "Plan"
    return plan


def _refresh_session_user(request, api):
    try:
        me_resp = api.get("/auth/me")
        request.session["user"] = me_resp.get("data") or request.session.get("user", {})
    except APIError:
        pass


class UpgradePlanView(View, APIViewMixin):
    template_name = "subscription/upgrade.html"

    def get(self, request):
        user = _current_user(request)
        user_type = _user_type(user)
        plans = []

        try:
            with get_api_client(request) as api:
                resp = api.get("/plans", params={"user_type": user_type})
                plans = [_normalize_plan(plan) for plan in resp.get("data", [])]
        except APIError as e:
            self.handle_api_error(request, None, e)

        return render(
            request,
            self.template_name,
            {
                "plans": plans,
                "user_type": user_type,
                "current_plan": user.get("subscription_plan") or user.get("plan"),
            },
        )

    def post(self, request):
        plan_id = request.POST.get("plan_id")
        amount = request.POST.get("amount") or 0
        user = _current_user(request)
        user_type = _user_type(user)

        if not plan_id:
            messages.error(request, "Please select a subscription plan.")
            return redirect("subscription:plans")

        try:
            with get_api_client(request) as api:
                api.post(
                    "/subscriptions/upgrade",
                    json={
                        "plan_id": str(plan_id),
                        "payment_id": f"internal_upg_{_user_id(user)}_{plan_id}",
                        "amount_paid": float(amount),
                        "currency": "USD",
                    },
                )
                _refresh_session_user(request, api)

            messages.success(request, f"Welcome to your new {user_type.title()} plan!")
            return redirect(f"dashboard:{user_type}")
        except (APIError, ValueError) as e:
            if isinstance(e, APIError):
                self.handle_api_error(request, None, e)
            else:
                messages.error(request, "Invalid plan amount.")
                return redirect("subscription:plans")


class ManageSubscriptionView(View, APIViewMixin):
    template_name = "subscription/manage.html"

    def get(self, request):
        current = None
        history = []

        try:
            with get_api_client(request) as api:
                current_resp = api.get("/subscriptions/current")
                history_resp = api.get("/subscriptions/history")
                current = current_resp.get("data")
                history = history_resp.get("data") or []
        except APIError as e:
            self.handle_api_error(request, None, e)

        return render(
            request,
            self.template_name,
            {
                "current": current,
                "history": history,
            },
        )


class ProcessSubscriptionView(View, APIViewMixin):
    def post(self, request):
        plan_id = request.POST.get("plan_id")
        action = request.POST.get("action") or "upgrade"
        amount = request.POST.get("amount") or 0

        if not plan_id:
            messages.error(request, "Please select a subscription plan.")
            return redirect("subscription:manage")

        endpoint = "/subscriptions/subscribe" if action == "subscribe" else "/subscriptions/upgrade"

        try:
            with get_api_client(request) as api:
                api.post(
                    endpoint,
                    json={
                        "plan_id": str(plan_id),
                        "payment_id": f"manual_proc_{plan_id}",
                        "amount_paid": float(amount),
                        "currency": "USD",
                    },
                )
                _refresh_session_user(request, api)

            messages.success(request, "Subscription updated successfully.")
        except (APIError, ValueError) as e:
            if isinstance(e, APIError):
                self.handle_api_error(request, None, e)
            else:
                messages.error(request, "Invalid payment amount.")

        return redirect("subscription:manage")

    def get(self, request):
        return redirect("subscription:manage")


class CancelSubscriptionView(View, APIViewMixin):
    def post(self, request):
        reason = request.POST.get("reason") or "User requested cancellation"

        try:
            with get_api_client(request) as api:
                api.post("/subscriptions/cancel", json={"reason": reason})
                _refresh_session_user(request, api)
            messages.info(request, "Subscription cancelled successfully.")
        except APIError as e:
            self.handle_api_error(request, None, e)

        return redirect("subscription:manage")

    def get(self, request):
        return redirect("subscription:manage")


class PlansListView(View, APIViewMixin):
    """Public listing of plans (filtered by user_type)."""
    template_name = "subscription/plans_list.html"

    def get(self, request):
        user = _current_user(request)
        user_type = _user_type(user)
        plans = []

        try:
            with get_api_client(request) as api:
                resp = api.get("/plans", params={"user_type": user_type})
                plans = [_normalize_plan(plan) for plan in resp.get("data", [])]
        except APIError as e:
            self.handle_api_error(request, None, e)

        return render(request, self.template_name, {"plans": plans, "user_type": user_type})


class PlanCreateView(View, APIViewMixin):
    template_name = "subscription/plan_form.html"

    def get(self, request):
        return render(request, self.template_name, {"action": "create"})

    def post(self, request):
        # Minimal form: name, price, description, user_type (client/provider)
        name = request.POST.get("name")
        price = request.POST.get("price")
        description = request.POST.get("description")
        user_type = request.POST.get("user_type") or "client"

        payload = {
            "name": name,
            "price": float(price) if price else 0,
            "description": description,
        }

        endpoint = "/plans/client" if user_type == "client" else "/plans/provider"

        try:
            with get_api_client(request) as api:
                api.post(endpoint, json=payload)
            messages.success(request, "Plan created successfully.")
            return redirect("subscription:plans")
        except (APIError, ValueError) as e:
            if isinstance(e, APIError):
                self.handle_api_error(request, None, e)
            else:
                messages.error(request, "Invalid price value.")
            return render(request, self.template_name, {"action": "create", "form": payload})


class PlanUpdateView(View, APIViewMixin):
    template_name = "subscription/plan_form.html"

    def get(self, request, plan_id):
        plan = None
        try:
            with get_api_client(request) as api:
                resp = api.get(f"/plans/{plan_id}")
                plan = resp.get("data")
        except APIError as e:
            self.handle_api_error(request, None, e)

        return render(request, self.template_name, {"action": "edit", "plan": plan})

    def post(self, request, plan_id):
        name = request.POST.get("name")
        price = request.POST.get("price")
        description = request.POST.get("description")

        payload = {"name": name, "price": float(price) if price else None, "description": description}

        try:
            with get_api_client(request) as api:
                api.put(f"/plans/{plan_id}", json=payload)
            messages.success(request, "Plan updated successfully.")
            return redirect("subscription:plans")
        except (APIError, ValueError) as e:
            if isinstance(e, APIError):
                self.handle_api_error(request, None, e)
            else:
                messages.error(request, "Invalid price value.")

            return render(request, self.template_name, {"action": "edit", "plan": payload})


class PlanDeleteView(View, APIViewMixin):
    def post(self, request, plan_id):
        try:
            with get_api_client(request) as api:
                api.delete(f"/plans/{plan_id}")
            messages.success(request, "Plan deleted.")
        except APIError as e:
            self.handle_api_error(request, None, e)

        return redirect("subscription:plans")


class AdminSubscriptionsListView(View, APIViewMixin):
    template_name = "subscription/admin_subscriptions.html"

    def get(self, request):
        subs = []
        try:
            with get_api_client(request) as api:
                resp = api.get("/subscriptions")
                subs = resp.get("data") or []
        except APIError as e:
            self.handle_api_error(request, None, e)

        return render(request, self.template_name, {"subscriptions": subs})


class SubscriptionDetailView(View, APIViewMixin):
    template_name = "subscription/subscription_detail.html"

    def get(self, request, subscription_id):
        sub = None
        try:
            with get_api_client(request) as api:
                resp = api.get(f"/subscriptions/{subscription_id}")
                sub = resp.get("data")
        except APIError as e:
            self.handle_api_error(request, None, e)

        return render(request, self.template_name, {"subscription": sub})


class TriggerExpiryView(View, APIViewMixin):
    def post(self, request):
        try:
            with get_api_client(request) as api:
                api.post("/subscriptions/expire")
            messages.success(request, "Expiry job triggered.")
        except APIError as e:
            self.handle_api_error(request, None, e)

        return redirect("subscription:admin_subscriptions")
