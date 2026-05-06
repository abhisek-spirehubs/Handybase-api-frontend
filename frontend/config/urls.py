from django.urls import path, include, re_path
from django.views.generic import RedirectView
from django.conf import settings

urlpatterns = [
    # Send people visiting the root URL to the landing page
    path('', RedirectView.as_view(pattern_name='auth:landing', permanent=False), name='home'),
    
    path('auth/', include('apps.authentication.urls', namespace='auth')),
    path('dashboard/', include('apps.dashboard.urls', namespace='dashboard')),
    path('subscription/', include('apps.subscription.urls', namespace='subscription')),
    path('services/', include('apps.service.urls', namespace='service')),
    path('i18n/', include('django.conf.urls.i18n')),
    path("reviews/", include("apps.reviews.urls")),
    path("client-reviews/", include("apps.client_reviews.urls", namespace="client_reviews")),
    path("notifications/", include("apps.notifications.urls", namespace="notifications")),
    path("chat/", include("apps.chat.urls", namespace="chat")),
]

if settings.DEBUG:
    # The frontend doesn't host media files, the FastAPI backend does.
    # Redirect all frontend /media/ requests to the backend server.
    fastapi_host = "/".join(settings.FASTAPI_BASE_URL.split("/")[:3])
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', RedirectView.as_view(url=f'{fastapi_host}/media/%(path)s', permanent=False)),
    ]