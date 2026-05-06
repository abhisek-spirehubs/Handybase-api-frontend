from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from apps.core.api_client import get_api_client, APIError
from apps.core.mixins import APIViewMixin


def normalize_ids(items):
    for item in items:
        if "_id" in item and "id" not in item:
            item["id"] = item["_id"]
    return items


# ─────────────────────────────────────────
# PROVIDER VIEWS (CRUD for Services)
# ─────────────────────────────────────────

class ProviderServiceListView(View, APIViewMixin):
    template_name = "service/provider_list.html"

    def get(self, request):
        user = request.session.get("user", {})
        if user.get("user_type") != "provider":
            return redirect("auth:login")

        services = []
        try:
            with get_api_client(request) as api:
                # GET /api/v1/services?provider_id=...
                # We fetch the provider's own services
                provider_id = user.get("id") or user.get("_id")
                resp = api.get("/services", params={"provider_id": provider_id, "limit": 50})
                services = resp.get("data", [])
                
                # Normalize IDs for template
                normalize_ids(services)
        except APIError as e:
            messages.error(request, f"Failed to load services: {e.detail}")

        return render(request, self.template_name, {"services": services})

    def post(self, request):
        """Handles deleting a service"""
        action = request.POST.get("action")
        service_id = request.POST.get("service_id")

        if action == "delete" and service_id:
            try:
                with get_api_client(request) as api:
                    api.delete(f"/services/{service_id}")
                messages.success(request, "Service deleted successfully.")
            except APIError as e:
                messages.error(request, f"Failed to delete service: {e.detail}")

        return redirect("service:provider_list")


class ProviderServiceCreateView(View, APIViewMixin):
    template_name = "service/provider_form.html"

    def get(self, request):
        # You would normally fetch categories here to populate a dropdown
        # GET /api/v1/categories
        categories = []
        try:
            with get_api_client(request) as api:
                resp = api.get("/categories", params={"limit": 100})
                categories = resp.get("data", [])
                normalize_ids(categories)
        except APIError:
            pass
            
        return render(request, self.template_name, {"categories": categories, "action": "Create"})

    def post(self, request):
        # Build form data expected by FastAPI Form(...)
        data = {
            "title": request.POST.get("title"),
            "description": request.POST.get("description", ""),
            "category_id": request.POST.get("category_id"),
            "price": request.POST.get("price"),
            "duration": request.POST.get("duration"),
            "city": request.POST.get("city", ""),
            "state": request.POST.get("state", ""),
        }
        
        files = {}
        image = request.FILES.get("image")
        if image:
            files["image"] = (image.name, image.file, image.content_type)

        try:
            with get_api_client(request) as api:
                # POST /api/v1/services
                api.post("/services", data=data, files=files if files else None)
            messages.success(request, "Service created successfully! It is now pending admin approval.")
            return redirect("service:provider_list")
        except APIError as e:
            messages.error(request, f"Failed to create service: {e.detail}")
            return redirect("service:provider_create")


class ProviderServiceEditView(View, APIViewMixin):
    template_name = "service/provider_form.html"

    def get(self, request, service_id):
        service = {}
        categories = []
        try:
            with get_api_client(request) as api:
                # Fetch categories for dropdown
                cat_resp = api.get("/categories", params={"limit": 100})
                categories = cat_resp.get("data", [])
                normalize_ids(categories)
                
                # Fetch single service data
                srv_resp = api.get(f"/services/{service_id}")
                service = srv_resp.get("data", {})
                if "_id" in service: service["id"] = service["_id"]
        except APIError as e:
            messages.error(request, "Failed to load service details.")
            return redirect("service:provider_list")

        return render(request, self.template_name, {
            "categories": categories, 
            "service": service,
            "action": "Edit"
        })

    def post(self, request, service_id):
        data = {
            "title": request.POST.get("title"),
            "description": request.POST.get("description", ""),
            "category_id": request.POST.get("category_id"),
            "price": request.POST.get("price"),
            "duration": request.POST.get("duration"),
            "city": request.POST.get("city", ""),
            "state": request.POST.get("state", ""),
        }
        
        files = {}
        image = request.FILES.get("image")
        if image:
            files["image"] = (image.name, image.file, image.content_type)

        try:
            with get_api_client(request) as api:
                # PUT /api/v1/services/{id}
                api.put(f"/services/{service_id}", data=data, files=files if files else None)
            messages.success(request, "Service updated successfully!")
            return redirect("service:provider_list")
        except APIError as e:
            messages.error(request, f"Failed to update service: {e.detail}")
            return redirect("service:provider_edit", service_id=service_id)


# ─────────────────────────────────────────
# ADMIN VIEWS (Approval Process)
# ─────────────────────────────────────────

class AdminServiceApprovalsView(View, APIViewMixin):
    template_name = "service/admin_approvals.html"

    def get(self, request):
        if request.session.get("user", {}).get("user_type") != "admin":
            return redirect("auth:login")

        services = []
        try:
            with get_api_client(request) as api:
                # Fetch only PENDING services
                resp = api.get("/services", params={"approval_status": "PENDING", "limit": 50})
                services = resp.get("data", [])
                normalize_ids(services)
        except APIError as e:
            messages.error(request, f"Failed to load pending services: {e.detail}")

        return render(request, self.template_name, {"services": services})

    def post(self, request):
        service_id = request.POST.get("service_id")
        action = request.POST.get("action") # 'approve' or 'reject'
        reason = request.POST.get("reason", "")

        try:
            with get_api_client(request) as api:
                # PATCH /api/v1/services/{service_id}/status
                api.patch(f"/services/{service_id}/status", json={
                    "action": action,
                    "reason": reason
                })
            messages.success(request, f"Service successfully {action}d.")
        except APIError as e:
            messages.error(request, f"Failed to process approval: {e.detail}")

        return redirect("service:admin_approvals")
