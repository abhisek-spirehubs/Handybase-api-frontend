from django import forms
import re

class UserProfileForm(forms.Form):
    fname = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "First Name"})
    )
    lname = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Last Name"})
    )
    phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Phone Number"})
    )

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if phone:
            # Strip invalid characters to match FastAPI regex requirements
            phone = re.sub(r'[^\+0-9]', '', phone)
        return phone