from django.urls import path
from . import views

app_name = 'service'

urlpatterns = [
    # Provider Routes
    path('my-services/', views.ProviderServiceListView.as_view(), name='provider_list'),
    path('my-services/create/', views.ProviderServiceCreateView.as_view(), name='provider_create'),
    path('my-services/<str:service_id>/edit/', views.ProviderServiceEditView.as_view(), name='provider_edit'),
    
    # Admin Routes
    path('admin/approvals/', views.AdminServiceApprovalsView.as_view(), name='admin_approvals'),
]