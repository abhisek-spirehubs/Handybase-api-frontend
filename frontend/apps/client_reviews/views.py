from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View
from django.utils.translation import gettext_lazy as _
from apps.core.api_client import APIError, get_api_client
from apps.core.mixins import APIViewMixin

class RateClientView(View, APIViewMixin):
    """View for providers to rate their clients after a completed booking."""
    template_name = "client_reviews/rate_client.html"

    def get(self, request, booking_id):
        booking = None
        try:
            with get_api_client(request) as api:
                resp = api.get(f"/bookings/{booking_id}")
                booking = resp.get("data")
        except APIError:
            messages.error(request, _("Could not fetch booking details."))
            return redirect("dashboard:provider_bookings")

        return render(request, self.template_name, {
            "booking_id": booking_id,
            "booking": booking,
        })

    def post(self, request, booking_id):
        rating = request.POST.get("rating")
        comment = request.POST.get("comment", "").strip()

        if not rating or not (1 <= float(rating) <= 5):
            messages.error(request, _("Please choose a rating between 1 and 5."))
            return redirect("client_reviews:rate", booking_id=booking_id)

        try:
            with get_api_client(request) as api:
                data = {
                    "booking_id": booking_id,
                    "rating": rating,
                    "comment": comment,
                }
                api.post("/client-review", json=data)
            
            messages.success(request, _("Thank you for rating your client!"))
        except APIError as e:
            self.handle_api_error(request, None, e)

        return redirect("dashboard:provider_bookings")


class ProviderClientReviewsView(View, APIViewMixin):
    """List all reviews a provider has given to their clients."""
    template_name = "client_reviews/provider_reviews_list.html"

    def get(self, request):
        reviews = []
        try:
            with get_api_client(request) as api:
                resp = api.get("/client-review")
                reviews = resp.get("data", [])
                for r in reviews:
                    if "_id" in r and "id" not in r:
                        r["id"] = r["_id"]
        except APIError as e:
            self.handle_api_error(request, None, e)

        return render(request, self.template_name, {"reviews": reviews})


class UpdateClientReviewView(View, APIViewMixin):
    """Edit a review given to a client."""
    template_name = "client_reviews/update_review.html"

    def get(self, request, review_id):
        return render(request, self.template_name, {"review_id": review_id})

    def post(self, request, review_id):
        rating = request.POST.get("rating")
        comment = request.POST.get("comment", "").strip()
        try:
            with get_api_client(request) as api:
                api.put(f"/client-review/{review_id}", json={
                    "rating": rating,
                    "comment": comment
                })
            messages.success(request, _("Review updated successfully."))
        except APIError as e:
            self.handle_api_error(request, None, e)
        return redirect("client_reviews:my_reviews")


class DeleteClientReviewView(View, APIViewMixin):
    """Delete a review given to a client."""

    def post(self, request, review_id):
        try:
            with get_api_client(request) as api:
                api.delete(f"/client-review/{review_id}")
            messages.info(request, _("Review deleted."))
        except APIError as e:
            self.handle_api_error(request, None, e)
        return redirect("client_reviews:my_reviews")


class ClientReceivedReviewsView(View, APIViewMixin):
    """List all reviews a client has received from providers."""
    template_name = "client_reviews/client_received_list.html"

    def get(self, request):
        reviews = []
        user = request.session.get("user", {})
        client_id = user.get("_id") or user.get("id")

        if not client_id:
            messages.error(request, _("User session expired."))
            return redirect("authentication:login")

        try:
            with get_api_client(request) as api:
                # Backend endpoint is GET /api/v1/client-review/{client_id}
                resp = api.get(f"/client-review/{client_id}")
                reviews = resp.get("data", [])
                for r in reviews:
                    if "_id" in r and "id" not in r:
                        r["id"] = r["_id"]
        except APIError as e:
            self.handle_api_error(request, None, e)

        return render(request, self.template_name, {"reviews": reviews})


class ClientGivenReviewsView(View, APIViewMixin):
    """List all reviews a client has given to providers (CRUD)."""
    template_name = "client_reviews/client_given_list.html"

    def get(self, request):
        reviews = []
        try:
            with get_api_client(request) as api:
                resp = api.get("/client-review")
                reviews = resp.get("data", [])
                for r in reviews:
                    if "_id" in r and "id" not in r:
                        r["id"] = r["_id"]
        except APIError:
            pass
        return render(request, self.template_name, {"reviews": reviews})
