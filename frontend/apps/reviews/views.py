from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.core.api_client import APIError, get_api_client
from apps.core.mixins import APIViewMixin


class ProviderReviewsView(View, APIViewMixin):
    """Public page that lists all reviews for a given provider."""
    template_name = "reviews/provider_reviews.html"

    def get(self, request, provider_id):
        # Fallback if the template couldn't find user.id
        if provider_id == "me" or "@" in provider_id:
            provider_id = request.session.get("user", {}).get("_id", provider_id)

        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 10))
        min_rating = request.GET.get("min_rating")

        reviews = []
        total = 0
        error = None

        try:
            with get_api_client(request) as api:
                params = {"page": page, "limit": limit}
                if min_rating:
                    params["min_rating"] = float(min_rating)
                resp = api.get(f"/reviews/{provider_id}", params=params)
                data = resp.get("data", [])
                total = resp.get("total", 0)
                reviews = data
        except APIError as e:
            error = self.handle_api_error(request, None, e)

        context = {
            "provider_id": provider_id,
            "reviews": reviews,
            "total": total,
            "page": page,
            "limit": limit,
            "min_rating": min_rating,
            "error": error,
        }
        return render(request, self.template_name, context)




class UpdateReviewView(View, APIViewMixin):
    """Edit an existing review (client only)."""
    template_name = "reviews/update_review.html"

    def get(self, request, review_id):
        # We render the update form. If the backend later supports GET /reviews/{review_id},
        # we can fetch the existing data to prepopulate it here.
        return render(request, self.template_name, {
            "review_id": review_id,
        })

    def post(self, request, review_id):
        rating = request.POST.get("rating")
        comment = request.POST.get("comment", "").strip()
        replace_media = request.POST.get("replace_media", "false").lower() == "true"
        media_files = request.FILES.getlist("media_files")

        try:
            with get_api_client(request) as api:
                data = {}
                if rating:
                    data["rating"] = rating
                if comment:
                    data["comment"] = comment
                if replace_media:
                    data["replace_media"] = "true"

                files = []
                for f in media_files:
                    files.append(("media_files", (f.name, f.read(), f.content_type)))

                api.put(f"/reviews/{review_id}", data=data, files=files)
            messages.success(request, _("Review updated."))
        except APIError as e:
            self.handle_api_error(request, None, e)

        return redirect(request.META.get("HTTP_REFERER", "/"))


class DeleteReviewView(View, APIViewMixin):
    """Delete own review."""
    def post(self, request, review_id):
        try:
            with get_api_client(request) as api:
                api.delete(f"/reviews/{review_id}")
            messages.info(request, _("Review deleted."))
        except APIError as e:
            self.handle_api_error(request, None, e)
        return redirect(request.META.get("HTTP_REFERER", "/"))



class CreateReviewView(View, APIViewMixin):
    template_name = "reviews/create_review.html"

    def get(self, request, booking_id):
        # Fetch booking info to show background (provider name, service)
        booking = None
        try:
            with get_api_client(request) as api:
                resp = api.get(f"/bookings/{booking_id}")
                booking = resp.get("data")
        except APIError:
            pass

        return render(request, self.template_name, {
            "booking_id": booking_id,
            "booking": booking,
        })

    def post(self, request, booking_id):
        rating = request.POST.get("rating")
        comment = request.POST.get("comment", "").strip()
        media_files = request.FILES.getlist("media_files")

        if not rating or not (1 <= float(rating) <= 5):
            messages.error(request, _("Please choose a rating between 1 and 5."))
            return redirect("dashboard:client_bookings")

        try:
            with get_api_client(request) as api:
                # Prepare multipart data
                files = []
                for f in media_files:
                    files.append(("media_files", (f.name, f.read(), f.content_type)))

                data = {
                    "rating": rating,
                    "comment": comment,
                }

                api.post(
                    f"/reviews/{booking_id}",
                    data=data,
                    files=files,
                )
                _refresh_session_user(request, api)   # if you need to update the session
            messages.success(request, _("Your review has been submitted. Thank you!"))
        except APIError as e:
            self.handle_api_error(request, None, e)

        return redirect("dashboard:client_bookings")



def _refresh_session_user(request, api):
    """Helper to refresh user in session after review changes."""
    try:
        me = api.get("/auth/me")
        request.session["user"] = me.get("data") or request.session.get("user", {})
    except APIError:
        pass


class AdminReviewsView(View, APIViewMixin):
    """Admin page to list all reviews across the platform."""
    template_name = "reviews/admin_reviews.html"

    def get(self, request):
        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 10))
        min_rating = request.GET.get("min_rating")
        provider_id = request.GET.get("provider_id")
        client_id = request.GET.get("client_id")
        include_deleted = request.GET.get("include_deleted", "false").lower() == "true"

        reviews = []
        total = 0
        error = None

        try:
            with get_api_client(request) as api:
                params = {"page": page, "limit": limit, "include_deleted": include_deleted}
                if min_rating:
                    params["min_rating"] = float(min_rating)
                if provider_id:
                    params["provider_id"] = provider_id
                if client_id:
                    params["client_id"] = client_id

                resp = api.get("/reviews/all", params=params)
                data = resp.get("data", [])
                total = resp.get("total", 0)
                reviews = data
        except APIError as e:
            error = self.handle_api_error(request, None, e)

        context = {
            "reviews": reviews,
            "total": total,
            "page": page,
            "limit": limit,
            "min_rating": min_rating,
            "provider_id": provider_id,
            "client_id": client_id,
            "include_deleted": include_deleted,
            "error": error,
        }
        return render(request, self.template_name, context)


class AdminDeleteReviewView(View, APIViewMixin):
    """Admin endpoint to delete any review."""
    def post(self, request, review_id):
        try:
            with get_api_client(request) as api:
                api.delete(f"/reviews/admin/{review_id}")
            messages.success(request, _("Review deleted by admin."))
        except APIError as e:
            self.handle_api_error(request, None, e)
        return redirect(request.META.get("HTTP_REFERER", reverse("reviews:admin_list")))