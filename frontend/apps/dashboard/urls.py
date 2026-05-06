from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # ── SHARED ROUTES ──────────────────────────────────────────────────────────
    # This handles BOTH Client and Provider profiles now!
    path('profile/', views.ProfileView.as_view(), name='profile'),
    
    # ── PROVIDER ROUTES ────────────────────────────────────────────────────────
    path('provider/', views.ProviderDashboardView.as_view(), name='provider'),
    path('provider/bookings/', views.ProviderBookingsView.as_view(), name='provider_bookings'), # <--- ADDED THIS
    
    # ── CLIENT ROUTES ──────────────────────────────────────────────────────────
    path('client/', views.ClientDashboardView.as_view(), name='client'),
    
    
    # Directory & Booking flow
    path('directory/', views.ProviderDirectoryView.as_view(), name='directory'),
    path('directory/<str:provider_id>/', views.ProviderDetailView.as_view(), name='provider_detail'),
    path('client/bookings/', views.ClientBookingsView.as_view(), name='client_bookings'),
    
    # ── ADMIN ROUTES ───────────────────────────────────────────────────────────
    path('admin/', views.AdminDashboardView.as_view(), name='admin'),
    path('admin/approvals/', views.AdminApprovalsView.as_view(), name='admin_approvals'),
    path('admin/clients/', views.AdminClientsView.as_view(), name='admin_clients'),
    path('admin/providers/', views.AdminProvidersView.as_view(), name='admin_providers'),
    path('admin/categories/', views.AdminCategoriesView.as_view(), name='admin_categories'),
    path('admin/bookings/', views.AdminBookingsView.as_view(), name='admin_bookings'), # <--- ADDED THIS
    path('set-language/', views.set_language, name='set_language'),

]