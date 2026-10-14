from django import forms
from .models import Job, Category, Skill

class JobForm(forms.ModelForm):
    category_input = forms.CharField(
        max_length=100, 
        required=False, 
        label="Category",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Software Engineering, Data Science'
        })
    )
    skills_input = forms.CharField(
        max_length=500,
        required=False,
        label="Required Skills",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Python, Django, PostgreSQL, REST API (comma-separated)'
        })
    )
    preferred_skills_input = forms.CharField(
        max_length=500,
        required=False,
        label="Preferred Skills",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Docker, AWS, Redis, React (comma-separated)'
        })
    )

    class Meta:
        model = Job
        fields = [
            'title', 'description', 'experience_years', 'education', 'openings',
            'salary_min', 'salary_max', 'location', 'employment_type',
            'work_model', 'deadline'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Senior Python Developer'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Provide a detailed overview of job responsibilities, requirements, and benefits...'}),
            'experience_years': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g. 3'}),
            'education': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "e.g. Bachelor's in Computer Science or equivalent"}),
            'openings': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': '1'}),
            'salary_min': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 500000'}),
            'salary_max': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 1200000'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Bangalore, India / Remote'}),
            'employment_type': forms.Select(attrs={'class': 'form-select'}),
            'work_model': forms.Select(attrs={'class': 'form-select'}),
            'deadline': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure default values for new job forms
        if not self.is_bound and not (self.instance and self.instance.pk):
            self.initial['openings'] = 1
            self.initial['experience_years'] = 0
            self.initial['employment_type'] = 'FULL_TIME'
            self.initial['work_model'] = 'ONSITE'

        if self.instance and self.instance.pk:
            if self.instance.category:
                self.initial['category_input'] = self.instance.category.name
            if self.instance.skills.exists():
                self.initial['skills_input'] = ', '.join([s.name for s in self.instance.skills.all()])
            if self.instance.preferred_skills.exists():
                self.initial['preferred_skills_input'] = ', '.join([s.name for s in self.instance.preferred_skills.all()])

    def clean(self):
        cleaned_data = super().clean()
        salary_min = cleaned_data.get('salary_min')
        salary_max = cleaned_data.get('salary_max')
        if salary_min is not None and salary_max is not None and salary_min > salary_max:
            self.add_error('salary_max', 'Maximum salary cannot be less than minimum salary.')
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Handle Category
        category_name = self.cleaned_data.get('category_input')
        if category_name:
            category, created = Category.objects.get_or_create(name__iexact=category_name, defaults={'name': category_name})
            instance.category = category
        else:
            instance.category = None
            
        if commit:
            instance.save()
            
            # Handle Required Skills
            skills_text = self.cleaned_data.get('skills_input', '')
            if skills_text:
                skill_names = [s.strip() for s in skills_text.split(',') if s.strip()]
                skill_objs = []
                for name in skill_names:
                    skill, _ = Skill.objects.get_or_create(name__iexact=name, defaults={'name': name})
                    skill_objs.append(skill)
                instance.skills.set(skill_objs)
            else:
                instance.skills.clear()

            # Handle Preferred Skills
            pref_text = self.cleaned_data.get('preferred_skills_input', '')
            if pref_text:
                pref_names = [s.strip() for s in pref_text.split(',') if s.strip()]
                pref_objs = []
                for name in pref_names:
                    skill, _ = Skill.objects.get_or_create(name__iexact=name, defaults={'name': name})
                    pref_objs.append(skill)
                instance.preferred_skills.set(pref_objs)
            else:
                instance.preferred_skills.clear()
            
        return instance

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category Name'}),
        }

