from django.urls import path
from . import views

app_name = "auth"

urlpatterns = [
	path("", views.LandingView.as_view(), name="landing"),
	path("login/", views.LoginView.as_view(), name="login"),
	path("logout/", views.LogoutView.as_view(), name="logout"),
	path("register/client/", views.ClientRegisterView.as_view(), name="register_client"),
	path("register/provider/", views.ProviderRegisterView.as_view(), name="register_provider"),
	path("pending-approval/", views.PendingApprovalView.as_view(), name="pending_approval"),
	path("forgot-password/", views.ForgotPasswordView.as_view(), name="forgot_password"),
	path("verify-otp/", views.VerifyOTPView.as_view(), name="verify_otp"),
	path("reset-password/", views.ResetPasswordView.as_view(), name="reset_password"),
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    path('verify-account/', views.VerifyAccountOTPView.as_view(), name='verify_account'),
    path('resend-otp/', views.ResendOTPView.as_view(), name='resend_otp'),
]
