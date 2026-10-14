from django import forms
from .models import Assessment, Question, AssessmentAssignment
from jobs.models import Job
from applications.models import Application

class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = ['title', 'description', 'duration_minutes', 'pass_percentage', 'job']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Senior Python Developer Skill Test'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Overview of this technical assessment'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 5, 'max': 180}),
            'pass_percentage': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100, 'step': 5}),
            'job': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, recruiter_company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if recruiter_company:
            self.fields['job'].queryset = Job.objects.filter(company=recruiter_company)

class QuestionForm(forms.ModelForm):
    options_text = forms.CharField(
        required=False, 
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Option 1\nOption 2\nOption 3\nOption 4'}),
        help_text="For MCQ: Enter each option on a new line."
    )

    class Meta:
        model = Question
        fields = ['question_type', 'text', 'marks', 'correct_answer', 'code_snippet', 'expected_output']
        widgets = {
            'question_type': forms.Select(attrs={'class': 'form-select'}),
            'text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter the question details...'}),
            'marks': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'correct_answer': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'For MCQ enter option number (0,1,2,3) or correct answer text'}),
            'code_snippet': forms.Textarea(attrs={'class': 'form-control font-monospace', 'rows': 4, 'placeholder': 'Initial code template (optional)'}),
            'expected_output': forms.Textarea(attrs={'class': 'form-control font-monospace', 'rows': 3, 'placeholder': 'Expected output or test case result'}),
        }

class AssignAssessmentForm(forms.Form):
    assessment = forms.ModelChoiceField(
        queryset=Assessment.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Select Assessment"
    )

    def __init__(self, *args, recruiter=None, **kwargs):
        super().__init__(*args, **kwargs)
        if recruiter:
            company = getattr(recruiter, 'company', None) or getattr(recruiter, 'owned_company', None)
            if company:
                qs = Assessment.objects.filter(created_by__company=company)
            else:
                qs = Assessment.objects.filter(created_by=recruiter)

            if recruiter.role == 'ADMIN' or not qs.exists():
                qs = Assessment.objects.all()

            self.fields['assessment'].queryset = qs.order_by('-created_at')
        else:
            self.fields['assessment'].queryset = Assessment.objects.all().order_by('-created_at')
