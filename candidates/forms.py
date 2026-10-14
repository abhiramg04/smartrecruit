import os
from django import forms
from .models import CandidateProfile

ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt']


class ResumeUploadForm(forms.ModelForm):
    class Meta:
        model = CandidateProfile
        fields = ['resume_file']

    def clean_resume_file(self):
        file = self.cleaned_data.get('resume_file')
        if file:
            ext = os.path.splitext(file.name)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise forms.ValidationError(
                    f"Invalid file type: '{ext}'. Only PDF, DOCX, and TXT files are supported."
                )
            # Limit file size to 5MB
            if file.size > 5 * 1024 * 1024:
                raise forms.ValidationError("File size must be under 5MB.")
        return file


class CandidateProfileForm(forms.ModelForm):
    skills_text = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Python, Django, SQL, React'}),
        help_text="Comma-separated list of skills"
    )

    class Meta:
        model = CandidateProfile
        fields = [
            'full_name', 'email', 'phone', 'location', 'summary',
            'linkedin_url', 'github_url'
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'linkedin_url': forms.URLInput(attrs={'class': 'form-control'}),
            'github_url': forms.URLInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.skills:
            if isinstance(self.instance.skills, list):
                self.fields['skills_text'].initial = ", ".join(self.instance.skills)
            elif isinstance(self.instance.skills, str):
                self.fields['skills_text'].initial = self.instance.skills

    def save(self, commit=True):
        profile = super().save(commit=False)
        skills_raw = self.cleaned_data.get('skills_text', '')
        if skills_raw:
            profile.skills = [s.strip() for s in skills_raw.split(',') if s.strip()]
        else:
            profile.skills = []
        if commit:
            profile.save()
        return profile

