from django import forms
from .models import SystemConfiguration

class SystemConfigurationForm(forms.ModelForm):
    class Meta:
        model = SystemConfiguration
        fields = ['site_name', 'support_email', 'maintenance_mode', 'allow_new_registrations']
        widgets = {
            'site_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. SmartRecruit'}),
            'support_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'e.g. support@smartrecruit.com'}),
            'maintenance_mode': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allow_new_registrations': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class AIConfigurationForm(forms.ModelForm):
    class Meta:
        from .models import AIConfiguration
        model = AIConfiguration
        fields = [
            'groq_api_key', 'default_model', 'fast_model', 'temperature', 'max_tokens',
            'resume_parser_prompt', 'ranking_prompt',
            'enable_resume_parsing', 'enable_ai_ranking', 'enable_interview_gen'
        ]
        widgets = {
            'groq_api_key': forms.PasswordInput(render_value=False, attrs={'class': 'form-control', 'placeholder': '•••••••• (Secret stored in Environment)'}),
            'default_model': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'openai/gpt-oss-120b'}),
            'fast_model': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'openai/gpt-oss-120b'}),
            'temperature': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0', 'max': '2'}),
            'max_tokens': forms.NumberInput(attrs={'class': 'form-control', 'min': '100', 'max': '32000'}),
            'resume_parser_prompt': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'ranking_prompt': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'enable_resume_parsing': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_ai_ranking': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_interview_gen': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class SecurityConfigurationForm(forms.ModelForm):
    class Meta:
        from .models import SecurityConfiguration
        model = SecurityConfiguration
        fields = ['enforce_strong_passwords', 'session_timeout_minutes', 'max_login_attempts', 'two_factor_auth_required']
        widgets = {
            'enforce_strong_passwords': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'session_timeout_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '1440'}),
            'max_login_attempts': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '100'}),
            'two_factor_auth_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
