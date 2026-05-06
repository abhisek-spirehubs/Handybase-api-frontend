from django.urls import path
from . import views

app_name = 'subscription'

urlpatterns = [
    path('upgrade/', views.UpgradePlanView.as_view(), name='upgrade'),
    path('manage/', views.ManageSubscriptionView.as_view(), name='manage'),
    path('process/', views.ProcessSubscriptionView.as_view(), name='process'),
    path('cancel/', views.CancelSubscriptionView.as_view(), name='cancel'),
    # Public plans listing
    path('plans/', views.PlansListView.as_view(), name='plans'),
    # Admin / CRUD for plans
    path('plans/create/', views.PlanCreateView.as_view(), name='plan_create'),
    path('plans/<str:plan_id>/edit/', views.PlanUpdateView.as_view(), name='plan_edit'),
    path('plans/<str:plan_id>/delete/', views.PlanDeleteView.as_view(), name='plan_delete'),
    # Admin subscriptions
    path('admin/', views.AdminSubscriptionsListView.as_view(), name='admin_subscriptions'),
    path('admin/trigger-expiry/', views.TriggerExpiryView.as_view(), name='trigger_expiry'),
    path('<str:subscription_id>/', views.SubscriptionDetailView.as_view(), name='detail'),
]
