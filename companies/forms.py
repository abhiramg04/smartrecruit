from django import forms
from .models import Company, Department

class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['name', 'industry', 'location', 'website']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['website'].required = False
        self.fields['industry'].required = False
        self.fields['location'].required = False

class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
