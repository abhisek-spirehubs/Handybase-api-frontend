from django.urls import path
from . import views

app_name = "client_reviews"

urlpatterns = [
    # Provider-side
    path("rate/<str:booking_id>/", views.RateClientView.as_view(), name="rate"),
    path("my-reviews/", views.ProviderClientReviewsView.as_view(), name="my_reviews"),
    
    # Client-side
    path("received/", views.ClientReceivedReviewsView.as_view(), name="received"),
    path("given/", views.ClientGivenReviewsView.as_view(), name="given"),
    
    # Shared CRUD (logic handled in views/api)
    path("<str:review_id>/update/", views.UpdateClientReviewView.as_view(), name="update"),
    path("<str:review_id>/delete/", views.DeleteClientReviewView.as_view(), name="delete"),
]
