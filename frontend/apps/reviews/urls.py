from django.urls import path
from . import views

app_name = "reviews"

urlpatterns = [
    # Public: list reviews for a provider
    path("provider/<str:provider_id>/", views.ProviderReviewsView.as_view(), name="provider_reviews"),

    # Create a review (booking_id is used)
    path("create/<str:booking_id>/", views.CreateReviewView.as_view(), name="create"),

    # Update / delete own review
    path("<str:review_id>/update/", views.UpdateReviewView.as_view(), name="update"),
    path("<str:review_id>/delete/", views.DeleteReviewView.as_view(), name="delete"),
    
    # Admin: manage all reviews
    path("admin/list/", views.AdminReviewsView.as_view(), name="admin_list"),
    path("admin/<str:review_id>/delete/", views.AdminDeleteReviewView.as_view(), name="admin_delete"),
]