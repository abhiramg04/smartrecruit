from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

# Roles available for public self-registration
# Admin accounts must be created via Django admin or createsuperuser
PUBLIC_ROLE_CHOICES = (
    ('CANDIDATE', 'Candidate'),
    ('RECRUITER', 'Recruiter'),
)

class CustomUserCreationForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=PUBLIC_ROLE_CHOICES,
        initial='CANDIDATE',
        widget=forms.HiddenInput()   # rendered visually via role cards in template
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'email', 'role')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True

    def clean_password1(self):
        # Bypass default UserCreationForm password validators (min length, similarity, etc.)
        return self.cleaned_data.get('password1')

    def clean_role(self):
        """Server-side guard: reject any attempt to register as ADMIN."""
        role = self.cleaned_data.get('role')
        allowed = [r[0] for r in PUBLIC_ROLE_CHOICES]
        if role not in allowed:
            raise forms.ValidationError(
                "Invalid role selected. Admin accounts cannot be self-registered."
            )
        return role

class OTPVerificationForm(forms.Form):
    otp = forms.CharField(max_length=6, min_length=6, required=True, label="Enter OTP")

class UserProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'bio', 'profile_photo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['profile_photo'].required = False
