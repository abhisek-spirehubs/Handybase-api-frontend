from apps.core.api_client import get_api_client, APIError

def unread_notifications(request):
    """
    Context processor to inject unread notification count globally.
    Safe-guarded to prevent page crashes on API failures.
    """
    if not request.session.get('user'):
        return {'unread_notifications_count': 0}
    
    try:
        # We use a short timeout for context processors to avoid hanging page loads
        with get_api_client(request) as api:
            resp = api.get("/notifications/unread-count")
            count = resp.get("count", 0)
            return {'unread_notifications_count': count}
    except Exception:
        # Silent fail for context processor to maintain UX stability
        return {'unread_notifications_count': 0}
