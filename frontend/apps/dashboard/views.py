from django.views import View
from django.shortcuts import render, redirect
from django.http import HttpRequest, HttpResponse
from django.contrib import messages
from django.conf import settings
from django.utils import translation
from urllib.parse import urlsplit, urlunsplit

from apps.core.api_client import get_api_client, APIError
from apps.core.mixins import APIViewMixin
from .forms import UserProfileForm


def normalize_ids(items):
    """
    Helper to map MongoDB '_id' to 'id' so Django templates 
    can access the primary key without triggering security blocks.
    """
    for item in items:
        if "_id" in item and "id" not in item:
            item["id"] = item["_id"]
    return items


def resolve_api_media_url(url):
    if not url or url.startswith(("http://", "https://", "data:")):
        return url

    api_base_url = getattr(
        settings,
        "API_BASE_URL",
        getattr(settings, "FASTAPI_BASE_URL", "http://127.0.0.1:8000/api/v1"),
    )
    parsed = urlsplit(api_base_url)
    api_origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    return f"{api_origin}{url if url.startswith('/') else '/' + url}"


def normalize_user_media_urls(user):
    for field in ("avatar_url", "profile_image"):
        if user.get(field):
            user[field] = resolve_api_media_url(user[field])

    if user.get("portfolio_images"):
        user["portfolio_images"] = [
            resolve_api_media_url(image)
            for image in user["portfolio_images"]
        ]

    return user


# ─────────────────────────────────────────
# DASHBOARD ENTRY VIEWS
# ─────────────────────────────────────────

class ProviderDashboardView(View):
    template_name = "dashboard/provider/overview.html"

    def get(self, request: HttpRequest):
        if not request.session.get("access_token"):
            return redirect("auth:login")

        user = request.session.get("user", {})
        if user.get("user_type") != "provider":
            return redirect("auth:login")

        raw_plan = user.get("subscription_plan", "provider_tier1")
        plan_mapping = {
            "provider_tier1": "Tier 1: Basic",
            "provider_tier2": "Tier 2: Standard",
            "provider_tier3": "Tier 3: Pro",
        }

        return render(
            request,
            self.template_name,
            {
                "user": user,
                "raw_plan": raw_plan,
                "display_plan": plan_mapping.get(raw_plan, "Tier 1: Basic"),
            },
        )


class ClientDashboardView(View):
    template_name = "dashboard/client/overview.html"

    def get(self, request: HttpRequest):
        if not request.session.get("access_token"):
            return redirect("auth:login")
        
        user = request.session.get("user", {})
        if user.get("user_type") != "client":
            return redirect("auth:login")

        # Determine if client is premium based on API plan data
        raw_plan = user.get("subscription_plan", "client_free")
        plan_mapping = {
            "client_free": "Basic Client",
            "client_paid": "Premium Client",
        }
        
        context = {
            "user": user,
            "raw_plan": raw_plan,
            "display_plan": plan_mapping.get(raw_plan, "Basic Client"),
            "is_premium": raw_plan == "client_paid", # Unlocks the dashboard cards
        }

        return render(request, self.template_name, context)


class AdminDashboardView(View, APIViewMixin):
    template_name = "dashboard/admin/overview.html"

    def get(self, request):
        user = request.session.get("user")
        
        if not user or user.get("user_type") != "admin":
            messages.error(request, "Unauthorized access.")
            return redirect("auth:login")

        dashboard_stats = {}
        try:
            with get_api_client(request) as api:
                response = api.get("/admin/dashboard")
                dashboard_stats = response.get("data", response)
        except APIError as e:
            error_msg = e.detail.get("message", "Could not load dashboard statistics.")
            messages.error(request, error_msg)

        return render(request, self.template_name, {
            "user": user,
            "stats": dashboard_stats
        })


# ─────────────────────────────────────────
# SHARED USER VIEWS
# ─────────────────────────────────────────

class ProfileView(View, APIViewMixin):
    template_name = "dashboard/shared/profile.html"

    def get(self, request):
        user = normalize_user_media_urls(dict(request.session.get("user", {})))
        
        # We pass the user data as 'profile' so the client template works seamlessly
        context = {
            "user": user,
            "profile": user 
        }
        return render(request, self.template_name, context)

    def post(self, request):
        user = request.session.get("user", {})
        user_type = user.get("user_type")
        
        if "delete_account" in request.POST:
            messages.error(request, "Account deletion must be requested through support or an admin.")
            return redirect("dashboard:profile")

        # Extract common fields
        fname = request.POST.get("fname", "").strip()
        lname = request.POST.get("lname", "").strip()
        phone = request.POST.get("phone", "").strip()
        
        # Extract Provider fields
        business_name = request.POST.get("business_name", "").strip()
        description = request.POST.get("description", "").strip()
        
        # Extract Client fields
        date_of_birth = request.POST.get("date_of_birth", "").strip()

        try:
            with get_api_client(request) as api:
                
                # ── CLIENT PROFILE UPDATE ────────────────────────────────────
                if user_type == "client":
                    form_data = {}
                    if fname: form_data["fname"] = fname
                    if lname: form_data["lname"] = lname
                    if phone: form_data["phone"] = phone
                    if date_of_birth: form_data["date_of_birth"] = date_of_birth
                    
                    files = None
                    # Client API schema expects the file to be named "avatar"
                    avatar_image = request.FILES.get("avatar") or request.FILES.get("profile_image")
                    if avatar_image:
                        avatar_image.file.seek(0)
                        files = {"avatar": (avatar_image.name, avatar_image.file, avatar_image.content_type)}
                    
                    api.put("/clients/update", data=form_data, files=files)

                # ── PROVIDER PROFILE UPDATE ──────────────────────────────────
                elif user_type == "provider":
                    if fname or lname:
                        api.put("/auth/profile", json={"fname": fname, "lname": lname})
                    
                    form_data = {}
                    if business_name: form_data["business_name"] = business_name
                    if description: form_data["description"] = description
                    if phone: form_data["phone"] = phone
                    
                    files = None
                    profile_image = request.FILES.get("profile_image")
                    if profile_image:
                        profile_image.file.seek(0)
                        files = {"profile_image": (profile_image.name, profile_image.file, profile_image.content_type)}
                    
                    api.put("/providers/update", data=form_data, files=files)

                # ── SYNC SESSION ─────────────────────────────────────────────
                # 1. Fetch base auth data
                auth_resp = api.get("/auth/me")
                updated_session_data = auth_resp.get("data", user)
                
                # 2. Fetch specific profile data to get the new Image URLs
                if user_type == "provider":
                    try:
                        prov_resp = api.get("/providers/me")
                        updated_session_data.update(prov_resp.get("data", {}))
                    except Exception:
                        pass
                elif user_type == "client":
                    try:
                        client_resp = api.get("/clients/profile")
                        updated_session_data.update(client_resp.get("data", {}))
                    except Exception:
                        pass

                # 3. Save the fully merged data back to the session
                request.session["user"] = normalize_user_media_urls(updated_session_data)
                request.session.modified = True
                
            messages.success(request, "Profile updated successfully!")
            return redirect("dashboard:profile")
            
        except APIError as e:
            error_detail = getattr(e, 'detail', str(e))
            messages.error(request, f"Error updating profile: {error_detail}")
            return redirect("dashboard:profile")


class ProviderDirectoryView(View):
    template_name = "dashboard/client/directory.html"

    def get(self, request: HttpRequest):
        if not request.session.get("access_token"):
            return redirect("auth:login")

        search_query = request.GET.get("search", "")
        params = {"limit": 20} 
        
        if search_query:
            params["search"] = search_query

        providers = []
        try:
            with get_api_client(request) as api:
                resp = api.get("/providers", params=params)
                providers = resp.get("data", [])
                
                # ---> ADD THIS LOOP SO THE TEMPLATE CAN READ THE ID <---
                for p in providers:
                    if "_id" in p and "id" not in p:
                        p["id"] = p["_id"]
                        
        except APIError as e:
            messages.error(request, f"Failed to load providers: {e.detail}")

        return render(request, self.template_name, {
            "providers": providers,
            "search_query": search_query
        })

# ─────────────────────────────────────────
# ADMIN MANAGEMENT VIEWS
# ─────────────────────────────────────────

class AdminClientsView(View, APIViewMixin):
    template_name = "dashboard/admin/clients.html"

    def get(self, request):
        if request.session.get("user", {}).get("user_type") != "admin":
            return redirect("auth:login")

        clients = []
        search = request.GET.get("search", "")
        try:
            with get_api_client(request) as api:
                params = {"limit": 50}
                if search: params["search"] = search
                resp = api.get("/clients", params=params)
                clients = resp.get("data", [])
                
                for c in clients:
                    if "_id" in c and "id" not in c:
                        c["id"] = c["_id"]
                        
        except APIError as e:
            self.handle_api_error(request, None, e)

        return render(request, self.template_name, {"clients": clients, "search": search})

    def post(self, request):
        action = request.POST.get("action")
        client_id = request.POST.get("client_id")
        
        try:
            with get_api_client(request) as api:
                if action == "delete":
                    api.delete(f"/clients/{client_id}")
                    messages.success(request, "Client deleted.")
                elif action in ["active", "inactive"]:
                    api.patch(f"/clients/{client_id}/status", json={"status": action})
                    messages.success(request, f"Client status updated to {action}.")
        except APIError as e:
            self.handle_api_error(request, None, e)
            
        return redirect("dashboard:admin_clients")


class AdminProvidersView(View, APIViewMixin):
    template_name = "dashboard/admin/providers.html"

    def get(self, request):
        if request.session.get("user", {}).get("user_type") != "admin":
            return redirect("auth:login")

        providers = []
        search = request.GET.get("search", "")
        try:
            with get_api_client(request) as api:
                params = {"limit": 50}
                if search: params["search"] = search
                resp = api.get("/providers/admin", params=params)
                providers = resp.get("data", [])
                
                for p in providers:
                    if "_id" in p and "id" not in p:
                        p["id"] = p["_id"]
                        
        except APIError as e:
            self.handle_api_error(request, None, e)

        return render(request, self.template_name, {"providers": providers, "search": search})

    def post(self, request):
        action = request.POST.get("action")
        provider_id = request.POST.get("provider_id")
        
        try:
            with get_api_client(request) as api:
                if action == "delete":
                    api.delete(f"/providers/{provider_id}")
                    messages.success(request, "Provider soft-deleted.")
                elif action == "restore":
                    api.post(f"/providers/{provider_id}/restore")
                    messages.success(request, "Provider restored.")
        except APIError as e:
            self.handle_api_error(request, None, e)
            
        return redirect("dashboard:admin_providers")


class AdminCategoriesView(View, APIViewMixin):
    template_name = "dashboard/admin/categories.html"

    def get(self, request):
        if request.session.get("user", {}).get("user_type") != "admin":
            return redirect("auth:login")

        categories = []
        try:
            with get_api_client(request) as api:
                resp = api.get("/categories", params={"limit": 50})
                categories = resp.get("data", [])
        except APIError as e:
            self.handle_api_error(request, None, e)

        return render(request, self.template_name, {"categories": categories})

    def post(self, request):
        action = request.POST.get("action")
        
        try:
            with get_api_client(request) as api:
                if action == "create":
                    api.post("/categories", data={
                        "name": request.POST.get("name"),
                        "description": request.POST.get("description")
                    })
                    messages.success(request, "Category created successfully.")
                    
                elif action == "delete":
                    cat_id = request.POST.get("category_id")
                    api.delete(f"/categories/{cat_id}")
                    messages.success(request, "Category deleted.")
                    
                elif action == "toggle_status":
                    cat_id = request.POST.get("category_id")
                    new_status = request.POST.get("status") 
                    api.patch(f"/categories/{cat_id}/status", json={"status": new_status})
                    messages.success(request, "Category status updated.")
                    
        except APIError as e:
            self.handle_api_error(request, None, e)
            
        return redirect("dashboard:admin_categories")
    

class AdminApprovalsView(View, APIViewMixin):
    template_name = "dashboard/admin/approvals.html"

    def get(self, request):
        if request.session.get("user", {}).get("user_type") != "admin":
            return redirect("auth:login")

        providers = []
        try:
            with get_api_client(request) as api:
                response = api.get("/providers/admin", params={"status": "pending", "limit": 50})
                providers = response.get("data", [])
                
                for p in providers:
                    if "_id" in p and "id" not in p:
                        p["id"] = p["_id"]
                        
        except APIError as e:
            self.handle_api_error(request, None, e)

        return render(request, self.template_name, {"providers": providers})

    def post(self, request):
        if request.session.get("user", {}).get("user_type") != "admin":
            return redirect("auth:login")

        provider_id = request.POST.get("provider_id")
        action = request.POST.get("action") 

        if not provider_id or action not in ["approve", "reject"]:
            messages.error(request, "Invalid action.")
            return redirect("dashboard:admin_approvals")

        try:
            with get_api_client(request) as api:
                api.patch(f"/providers/{provider_id}/status", json={"action": action})
            messages.success(request, f"Provider successfully {action}d!")
        except APIError as e:
            self.handle_api_error(request, None, e)

        return redirect("dashboard:admin_approvals")
    


class ProviderDetailView(View, APIViewMixin):
    template_name = "dashboard/client/provider_detail.html"

    def get(self, request, provider_id):
        if not request.session.get("access_token"):
            return redirect("auth:login")

        provider = {}
        services = []
        try:
            with get_api_client(request) as api:
                # 1. Fetch provider details
                resp = api.get(f"/providers/{provider_id}")
                provider = resp.get("data", {})

        except APIError as e:
            messages.error(request, "Provider not found or unavailable.")
            return redirect("dashboard:directory")

        try:
            with get_api_client(request) as api:
                # 2. Fetch provider's active services for the dropdown menu.
                # If the services endpoint fails, keep the provider profile usable.
                services_resp = api.get("/services", params={"provider_id": provider_id, "limit": 50})
                services = services_resp.get("data", [])
                
                # Ensure IDs are accessible in the template
                for s in services:
                    if "_id" in s and "id" not in s:
                        s["id"] = s["_id"]
                        
        except APIError as e:
            messages.warning(request, "Provider details loaded, but services are temporarily unavailable.")

        from datetime import date
        return render(request, self.template_name, {
            "provider": provider,
            "services": services,
            "today_date": date.today().isoformat(),  # e.g. "2026-05-05" for min date
        })

    def post(self, request, provider_id):
        service_id = request.POST.get("service_id")
        if not service_id:
            messages.error(request, "Please select an available service before booking.")
            return redirect("dashboard:provider_detail", provider_id=provider_id)

        # Combine separate date + time fields into ISO 8601 format for the API
        raw_date = request.POST.get("booking_date")   # e.g. "2026-05-26"
        raw_time = request.POST.get("booking_time")   # e.g. "14:30"
        if raw_date and raw_time:
            iso_date = f"{raw_date}T{raw_time}:00"
        elif raw_date:
            iso_date = f"{raw_date}T09:00:00"  # fallback default time
        else:
            iso_date = None

        booking_data = {
            "service_id": service_id,
            "booking_date": iso_date,
            "note": request.POST.get("note", ""),
            "address_line1": request.POST.get("address_line1"),
            "city": request.POST.get("city"),
            "state": request.POST.get("state"),
            "postal_code": request.POST.get("postal_code"),
            "country": request.POST.get("country", "India"),
        }

        try:
            with get_api_client(request) as api:
                api.post("/bookings", json=booking_data)
                
            messages.success(request, "Booking requested successfully! The provider will be notified.")
            return redirect("dashboard:client_bookings")
            
        except APIError as e:
            error_msg = getattr(e, 'detail', str(e))
            messages.error(request, f"Failed to place booking: {error_msg}")
            return redirect("dashboard:provider_detail", provider_id=provider_id)


# ─────────────────────────────────────────
# CLIENT BOOKINGS VIEW
# ─────────────────────────────────────────
# ─────────────────────────────────────────
# CLIENT BOOKINGS VIEW
# ─────────────────────────────────────────
class ClientBookingsView(View, APIViewMixin):
    template_name = "dashboard/client/bookings.html"

    def get(self, request):
        # Basic Auth Check
        if not request.session.get("access_token"):
            return redirect("auth:login")
        
        user = request.session.get("user", {})
        if user.get("user_type") != "client":
            return redirect("dashboard:provider")

        bookings = []
        try:
            with get_api_client(request) as api:
                # GET /api/v1/bookings (FastAPI filters this by the current user token)
                resp = api.get("/bookings", params={"limit": 50})
                bookings = resp.get("data", [])
                
                # Normalize MongoDB _id to id for the template
                normalize_ids(bookings)
                
        except APIError as e:
            messages.error(request, f"Could not load bookings: {getattr(e, 'detail', str(e))}")

        return render(request, self.template_name, {
            "user": user,
            "bookings": bookings
        })

    def post(self, request):
        """
        Handles Cancellation and Deletion from the Client side.
        """
        action = request.POST.get("action")
        booking_id = request.POST.get("booking_id")
        
        # Reason is required by the FastAPI backend for status transitions to CANCELLED
        reason = request.POST.get("cancellation_reason") or "Cancelled by client."

        try:
            with get_api_client(request) as api:
                if action == "cancel":
                    # PATCH /api/v1/bookings/{booking_id}/status
                    api.patch(f"/bookings/{booking_id}/status", json={
                        "booking_status": "CANCELLED",
                        "cancellation_reason": reason
                    })
                    messages.success(request, "Booking cancelled successfully.")
                    
                elif action == "delete":
                    # DELETE /api/v1/bookings/{booking_id}
                    api.delete(f"/bookings/{booking_id}")
                    messages.success(request, "Booking removed from your history.")
                    
        except APIError as e:
            messages.error(request, f"Action failed: {getattr(e, 'detail', str(e))}")

        return redirect("dashboard:client_bookings")

# ─────────────────────────────────────────
# PROVIDER BOOKINGS VIEW
# ─────────────────────────────────────────
class ProviderBookingsView(View, APIViewMixin):
    template_name = "dashboard/provider/bookings.html"

    def get(self, request):
        if request.session.get("user", {}).get("user_type") != "provider":
            return redirect("auth:login")

        from datetime import datetime

        bookings = []
        try:
            with get_api_client(request) as api:
                resp = api.get("/bookings", params={"limit": 50})
                bookings = resp.get("data", [])
                normalize_ids(bookings)

                # Parse booking_date ISO strings → Python datetime objects
                # so that |date and |time template filters work correctly
                for b in bookings:
                    raw = b.get("booking_date")
                    if raw and isinstance(raw, str):
                        # Handle both "2026-05-05T14:30:00" and "2026-05-05T14:30:00Z"
                        raw_clean = raw.replace("Z", "").split(".")[0]  # strip Z and microseconds
                        try:
                            b["booking_date"] = datetime.fromisoformat(raw_clean)
                        except ValueError:
                            pass  # leave as string if format is unexpected

        except APIError as e:
            messages.error(request, f"Failed to load bookings: {getattr(e, 'detail', str(e))}")

        return render(request, self.template_name, {"bookings": bookings})

    def post(self, request):
        action = request.POST.get("action")
        booking_id = request.POST.get("booking_id")
        reason = request.POST.get("cancellation_reason", "")

        status_map = {
            "confirm": "CONFIRMED",
            "complete": "COMPLETED",
            "cancel": "CANCELLED"
        }

        if action in status_map:
            try:
                with get_api_client(request) as api:
                    api.patch(f"/bookings/{booking_id}/status", json={
                        "booking_status": status_map[action],
                        "cancellation_reason": reason if action == "cancel" else None
                    })
                messages.success(request, f"Booking {action}ed successfully!")
            except APIError as e:
                messages.error(request, f"Action failed: {getattr(e, 'detail', str(e))}")

        return redirect("dashboard:provider_bookings")

# ─────────────────────────────────────────
# ADMIN BOOKINGS VIEW
# ─────────────────────────────────────────
class AdminBookingsView(View, APIViewMixin):
    template_name = "dashboard/admin/bookings.html"

    def get(self, request):
        if request.session.get("user", {}).get("user_type") != "admin":
            return redirect("auth:login")

        bookings = []
        try:
            with get_api_client(request) as api:
                # Backend returns all bookings for Admin
                resp = api.get("/bookings", params={"limit": 100})
                bookings = resp.get("data", [])
                normalize_ids(bookings)
        except APIError as e:
            messages.error(request, f"Failed to load bookings: {getattr(e, 'detail', str(e))}")

        return render(request, self.template_name, {"bookings": bookings})




def set_language(request):
    """Fallback language switcher for dashboard-scoped URLs."""
    lang_code = request.POST.get('language')
    
    if lang_code in [lang[0] for lang in settings.LANGUAGES]:
        translation.activate(lang_code)
        response = redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "/")
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME, 
            lang_code,
            max_age=365 * 24 * 60 * 60
        )
        return response
        
    return HttpResponse(status=400)
