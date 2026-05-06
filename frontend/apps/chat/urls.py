from django.urls import path
from . import views

app_name = "chat"

urlpatterns = [
    path("", views.ConversationListView.as_view(), name="list"),
    path("<str:booking_id>/", views.ChatRoomView.as_view(), name="room"),
]
