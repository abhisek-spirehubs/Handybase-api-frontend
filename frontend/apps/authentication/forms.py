"""
forms.py — Auth forms.
"""
import re
from django import forms


def _validate_password(password: str) -> str:
    if len(password) < 8:
        raise forms.ValidationError("Password must be at least 8 characters.")
    if not re.search(r"[A-Z]", password):
        raise forms.ValidationError("Password must contain at least one uppercase letter.")
    if not re.search(r"[0-9]", password):
        raise forms.ValidationError("Password must contain at least one number.")
    return password


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "you@example.com", "class": "form-input"})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Password", "class": "form-input"})
    )


class ClientRegisterForm(forms.Form):
    fname = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "First name", "class": "form-input"}),
    )
    lname = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "Last name", "class": "form-input"}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "you@example.com", "class": "form-input"}),
    )
    phone = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={"placeholder": "Phone (optional)", "class": "form-input"}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Password", "class": "form-input"}),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm password", "class": "form-input"}),
    )

    def clean_password(self):
        return _validate_password(self.cleaned_data["password"])

    def clean_phone(self):
        # STRIPS INVALID CHARACTERS SO IT MATCHES FASTAPI REGEX: ^\+?[0-9]{10,15}$
        phone = self.cleaned_data.get("phone")
        if phone:
            phone = re.sub(r'[^\+0-9]', '', phone)
        return phone

    def clean(self):
        cleaned = super().clean()
        pw  = cleaned.get("password")
        cpw = cleaned.get("confirm_password")
        if pw and cpw and pw != cpw:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned


class ProviderRegisterForm(forms.Form):
    fname = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "First name", "class": "form-input"}),
    )
    lname = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "Last name", "class": "form-input"}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "you@example.com", "class": "form-input"}),
    )
    phone = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={"placeholder": "Phone (optional)", "class": "form-input"}),
    )
    business_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Business name", "class": "form-input"}),
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"placeholder": "Briefly describe your services", "class": "form-input", "rows": 3}),
    )
    experience_years = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=60,
        widget=forms.NumberInput(attrs={"placeholder": "Years of experience", "class": "form-input"}),
    )
    address = forms.CharField(
        required=False,
        max_length=300,
        widget=forms.TextInput(attrs={"placeholder": "Service area / address", "class": "form-input"}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Password", "class": "form-input"}),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm password", "class": "form-input"}),
    )

    def clean_password(self):
        return _validate_password(self.cleaned_data["password"])

    def clean_phone(self):
        # Defensive check for provider phones too
        phone = self.cleaned_data.get("phone")
        if phone:
            phone = re.sub(r'[^\+0-9]', '', phone)
        return phone

    def clean(self):
        cleaned = super().clean()
        pw  = cleaned.get("password")
        cpw = cleaned.get("confirm_password")
        if pw and cpw and pw != cpw:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "Enter your registered email", "class": "form-input"}),
    )

class VerifyOTPForm(forms.Form):
    email = forms.EmailField(widget=forms.HiddenInput())
    otp = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={"placeholder": "Enter 6-digit OTP", "class": "form-input otp-input", "inputmode": "numeric"}),
    )

    def clean_otp(self):
        otp = self.cleaned_data["otp"].strip()
        if not otp.isdigit():
            raise forms.ValidationError("OTP must be 6 digits.")
        return otp

class ResetPasswordForm(forms.Form):
    email = forms.EmailField(widget=forms.HiddenInput())
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "New password", "class": "form-input"}),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm new password", "class": "form-input"}),
    )

    def clean_new_password(self):
        return _validate_password(self.cleaned_data["new_password"])

    def clean(self):
        cleaned = super().clean()
        pw  = cleaned.get("new_password")
        cpw = cleaned.get("confirm_password")
        if pw and cpw and pw != cpw:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned
    

class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-input"}))
    new_password = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-input"}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-input"}))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("new_password") != cleaned.get("confirm_password"):
            self.add_error("confirm_password", "New passwords do not match.")
        return cleaned