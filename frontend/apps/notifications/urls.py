from django.urls import path
from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.NotificationListView.as_view(), name="list"),
    path("<str:notification_id>/read/", views.MarkNotificationReadView.as_view(), name="mark_read"),
    path("read-all/", views.MarkAllReadView.as_view(), name="mark_all_read"),
    path("api/latest/", views.LatestNotificationsJSONView.as_view(), name="api_latest"),
]
