from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from apps.core.api_client import get_api_client, APIError
from apps.core.mixins import APIViewMixin

class NotificationListView(View, APIViewMixin):
    """
    Enterprise-grade view for listing user notifications.
    Supports pagination and displays unread status clearly.
    """
    template_name = "notifications/list.html"

    def get(self, request):
        page = request.GET.get("page", 1)
        limit = request.GET.get("limit", 20)
        
        notifications = []
        total = 0
        
        try:
            with get_api_client(request) as api:
                resp = api.get("/notifications", params={"page": page, "limit": limit})
                notifications = resp.get("data", [])
                total = resp.get("total", 0)
                
                # Normalize MongoDB _id to id for Django templates
                for n in notifications:
                    if "_id" in n and "id" not in n:
                        n["id"] = n["_id"]
        except APIError as e:
            self.handle_api_error(request, None, e)
            
        page_int = int(page)
        limit_int = int(limit)
        start_index = (page_int - 1) * limit_int + 1 if total > 0 else 0
        end_index = min(page_int * limit_int, total)

        context = {
            "notifications": notifications,
            "total": total,
            "page": page_int,
            "limit": limit_int,
            "start_index": start_index,
            "end_index": end_index,
        }
        return render(request, self.template_name, context)

from django.http import JsonResponse

class LatestNotificationsJSONView(View, APIViewMixin):
    """
    AJAX endpoint for polling new notifications.
    Returns the unread count and the most recent unread notification.
    """
    def get(self, request):
        if not request.session.get('user'):
            return JsonResponse({'count': 0, 'latest': None})
            
        try:
            with get_api_client(request) as api:
                # 1. Get count
                count_resp = api.get("/notifications/unread-count")
                count = count_resp.get("count", 0)
                
                # 2. Get latest unread
                latest = None
                if count > 0:
                    recent_resp = api.get("/notifications", params={"limit": 1})
                    data = recent_resp.get("data", [])
                    if data:
                        latest = data[0]
                        # Normalize ID
                        latest['id'] = latest.get('_id', latest.get('id'))
                
                return JsonResponse({
                    'count': count,
                    'latest': latest
                })
        except Exception:
            return JsonResponse({'count': 0, 'latest': None})

class MarkNotificationReadView(View, APIViewMixin):
    """
    Action view to mark a specific notification as read.
    Redirects back to the previous page or notification list.
    """
    def post(self, request, notification_id):
        try:
            with get_api_client(request) as api:
                api.patch(f"/notifications/{notification_id}/read")
        except APIError as e:
            self.handle_api_error(request, None, e)
            
        return redirect(request.META.get('HTTP_REFERER', 'notifications:list'))

class MarkAllReadView(View, APIViewMixin):
    """
    Bulk action view to clear all unread notifications.
    """
    def post(self, request):
        try:
            with get_api_client(request) as api:
                api.patch("/notifications/read-all")
            messages.success(request, _("All notifications marked as read."))
        except APIError as e:
            self.handle_api_error(request, None, e)
            
        return redirect('notifications:list')
