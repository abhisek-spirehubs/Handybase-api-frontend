"""
views.py — Authentication views.
"""
from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpRequest

# Update this line
from apps.core.api_client import get_anon_client, get_api_client, APIError
from .forms import (
    LoginForm,
    ClientRegisterForm,
    ProviderRegisterForm,
    ForgotPasswordForm,
    VerifyOTPForm,
    ResetPasswordForm,
    ChangePasswordForm,
)
from django.contrib import messages

# ── Mixin for Professional Error Handling ────────────────────────────────────
class APIViewMixin:
    """
    Mixin to handle API errors consistently across all auth views.
    """
    def handle_api_error(self, request, form, e):
        # e.detail is the dictionary from _extract_detail()
        error_data = e.detail 
        
        # 1. Handle Field-Specific Errors
        field_errors = error_data.get("field_errors", [])
        if field_errors:
            for err in field_errors:
                field = err.get("field")
                msg = err.get("message")
                # Attach to specific form field if it exists
                if field and field in form.fields:
                    form.add_error(field, msg)
                else:
                    # Fallback to non-field error
                    form.add_error(None, f"{field}: {msg}")
        
        # 2. Handle Global Message
        msg = error_data.get("message")
        if msg:
            messages.error(request, msg)
            # Only add to form if it wasn't already covered by field errors
            if not field_errors:
                form.add_error(None, msg)

# ── Endpoint constants ────────────────────────────────────────────────────────
LOGIN_ENDPOINT              = "/auth/login"
CLIENT_REGISTER_ENDPOINT    = "/clients"
PROVIDER_REGISTER_ENDPOINT  = "/providers/register"
SEND_OTP_ENDPOINT           = "/auth/send-otp"
VERIFY_OTP_ENDPOINT         = "/auth/verify-otp"
RESET_PASSWORD_ENDPOINT     = "/auth/change-password-with-otp"


def _store_session(request: HttpRequest, token: str, user: dict) -> None:
    request.session.cycle_key()
    request.session["access_token"] = token
    if "_id" in user and "id" not in user:
        user["id"] = user["_id"]
    request.session["user"] = user


class LandingView(View):
    template_name = "authentication/landing.html"
    def get(self, request: HttpRequest):
        if request.session.get("access_token"):
            return _redirect_after_login(request.session.get("user", {}))
        return render(request, self.template_name)


class LoginView(View, APIViewMixin):
    template_name = "authentication/login.html"

    def get(self, request: HttpRequest):
        if request.session.get("access_token"):
            return _redirect_after_login(request.session.get("user", {}))
        return render(request, self.template_name, {"form": LoginForm()})

    def post(self, request: HttpRequest):
        form = LoginForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        try:
            with get_anon_client() as api:
                token_resp = api.post(LOGIN_ENDPOINT, json={
                    "email":    form.cleaned_data["email"],
                    "password": form.cleaned_data["password"],
                })
                token = token_resp["data"]["access_token"]
                
                # Fetch user details
                from apps.core.api_client import APIClient
                with APIClient(token=token) as auth_api:
                    me_resp = auth_api.get("/auth/me")
                    user = me_resp["data"]

            _store_session(request, token, user)
            return _redirect_after_login(user)

        except APIError as e:
            # Auto-detect "Not Verified"
            error_str = str(e.detail).lower()
            if "not verified" in error_str or "verify email" in error_str:
                request.session["registered_email"] = form.cleaned_data["email"]
                messages.warning(request, "Your email is not verified. Please verify to continue.")
                return redirect("auth:verify_account")
                
            elif e.status_code == 403 and "not approved" in error_str:
                form.add_error(None, "Your provider account is pending admin approval.")
            else:
                self.handle_api_error(request, form, e)
            return render(request, self.template_name, {"form": form})

def _redirect_after_login(user: dict):
    role = user.get("user_type", "client")
    if role == "admin":
        return redirect("/dashboard/admin/")
    if role == "provider":
        return redirect("/dashboard/provider/")
    return redirect("/dashboard/client/")


class ClientRegisterView(View, APIViewMixin):
    template_name = "authentication/register_client.html"

    def get(self, request: HttpRequest):
        return render(request, self.template_name, {"form": ClientRegisterForm()})

    def post(self, request: HttpRequest):
        form = ClientRegisterForm(request.POST) 
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        try:
            with get_anon_client() as api:
                api.post(CLIENT_REGISTER_ENDPOINT, json=form.cleaned_data)
            
            request.session["registered_email"] = form.cleaned_data["email"]
            
            # CRITICAL FIX: This line flushes any old, stuck messages (like logout/password reset)
            list(messages.get_messages(request)) 
            
            messages.success(request, "Registration successful! Please check your email for the OTP.")
            return redirect("auth:verify_account")
            
        except APIError as e:
            self.handle_api_error(request, form, e)
            return render(request, self.template_name, {"form": form})


class ProviderRegisterView(View, APIViewMixin):
    template_name = "authentication/register_provider.html"

    def get(self, request: HttpRequest):
        return render(request, self.template_name, {"form": ProviderRegisterForm()})

    def post(self, request: HttpRequest):
        form = ProviderRegisterForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        try:
            with get_anon_client() as api:
                api.post(PROVIDER_REGISTER_ENDPOINT, data=form.cleaned_data)
            
            request.session["registered_email"] = form.cleaned_data["email"]
            
            # CRITICAL FIX: Flush old messages here too
            list(messages.get_messages(request)) 
            
            messages.success(request, "Registration submitted! Please verify your email with the OTP sent to you.")
            return redirect("auth:verify_account")
            
        except APIError as e:
            self.handle_api_error(request, form, e)
            return render(request, self.template_name, {"form": form})
        
class PendingApprovalView(View):
    template_name = "authentication/pending_approval.html"
    def get(self, request: HttpRequest):
        return render(request, self.template_name)


class LogoutView(View):
    def post(self, request: HttpRequest):
        token = request.session.get("access_token")
        if token:
            try:
                from apps.core.api_client import APIClient
                with APIClient(token=token) as api:
                    api.post("/auth/logout")
            except APIError:
                pass
        request.session.flush()
        messages.success(request, "You have been logged out.")
        return redirect("auth:login")


class ForgotPasswordView(View, APIViewMixin):
    template_name = "authentication/forgot_password.html"

    def get(self, request: HttpRequest):
        return render(request, self.template_name, {"form": ForgotPasswordForm()})

    def post(self, request: HttpRequest):
        form = ForgotPasswordForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        try:
            with get_anon_client() as api:
                api.post(SEND_OTP_ENDPOINT, json={"email": form.cleaned_data["email"]})
            request.session["otp_email"] = form.cleaned_data["email"]
            return redirect("auth:verify_otp")
        except APIError as e:
            self.handle_api_error(request, form, e)
            return render(request, self.template_name, {"form": form})


class VerifyOTPView(View, APIViewMixin):
    template_name = "authentication/verify_otp.html"

    def get(self, request: HttpRequest):
        email = request.session.get("otp_email", "")
        return render(request, self.template_name, {"form": VerifyOTPForm(initial={"email": email}), "email": email})

    def post(self, request: HttpRequest):
        form = VerifyOTPForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        try:
            with get_anon_client() as api:
                api.post(VERIFY_OTP_ENDPOINT, json=form.cleaned_data)
            request.session["otp_verified"] = True
            return redirect("auth:reset_password")
        except APIError as e:
            self.handle_api_error(request, form, e)
            return render(request, self.template_name, {"form": form})


class ResetPasswordView(View, APIViewMixin):
    template_name = "authentication/reset_password.html"

    def get(self, request: HttpRequest):
        if not request.session.get("otp_verified"):
            return redirect("auth:forgot_password")
        return render(request, self.template_name, {"form": ResetPasswordForm(initial={"email": request.session.get("otp_email")})})

    def post(self, request: HttpRequest):
        form = ResetPasswordForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        try:
            with get_anon_client() as api:
                api.post(RESET_PASSWORD_ENDPOINT, json=form.cleaned_data)
            request.session.pop("otp_email", None)
            request.session.pop("otp_verified", None)
            messages.success(request, "Password reset successful.")
            return redirect("auth:login")
        except APIError as e:
            self.handle_api_error(request, form, e)
            return render(request, self.template_name, {"form": form})


class ChangePasswordView(View, APIViewMixin):
    template_name = "authentication/change_password.html"

    def get(self, request):
        return render(request, self.template_name, {"form": ChangePasswordForm()})

    def post(self, request):
        form = ChangePasswordForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        try:
            with get_api_client(request) as api:
                api.patch("/auth/change-password", json={
                    "old_password": form.cleaned_data["old_password"],
                    "new_password": form.cleaned_data["new_password"]
                })
            messages.success(request, "Password updated successfully!")
            return redirect("dashboard:profile")
        except APIError as e:
            self.handle_api_error(request, form, e)
            return render(request, self.template_name, {"form": form})
        

class VerifyAccountOTPView(View, APIViewMixin):
    template_name = "authentication/verify_account.html"

    def get(self, request: HttpRequest):
        # Grab the email saved during registration
        email = request.session.get("registered_email", "")
        if not email:
            messages.warning(request, "Please register or log in first.")
            return redirect("auth:login")
            
        form = VerifyOTPForm(initial={"email": email})
        return render(request, self.template_name, {"form": form, "email": email})

    def post(self, request: HttpRequest):
        form = VerifyOTPForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        try:
            with get_anon_client() as api:
                # Calls your EXISTING backend route without any backend changes
                api.post(VERIFY_OTP_ENDPOINT, json={
                    "email": form.cleaned_data["email"],
                    "otp": form.cleaned_data["otp"]
                })
            
            # Clear the session data
            request.session.pop("registered_email", None)
            
            messages.success(request, "Email verified successfully! You can now log in.")
            return redirect("auth:login")
            
        except APIError as e:
            self.handle_api_error(request, form, e)
            return render(request, self.template_name, {"form": form, "email": form.cleaned_data.get("email")})
        

class ResendOTPView(View, APIViewMixin):
    def post(self, request: HttpRequest):
        email = request.session.get("registered_email")
        if not email:
            messages.error(request, "No email found. Please register again.")
            return redirect("auth:login")
        
        try:
            with get_anon_client() as api:
                # Reusing the existing send-otp endpoint
                api.post(SEND_OTP_ENDPOINT, json={"email": email})
            messages.success(request, "A new OTP has been sent to your email.")
        except APIError as e:
            self.handle_api_error(request, None, e)
            
        return redirect("auth:verify_account")