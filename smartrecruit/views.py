from django.shortcuts import render
from jobs.models import Job

def home(request):
    """Render the public landing page with latest job postings."""
    latest_jobs = Job.objects.filter(is_published=True, is_closed=False).order_by('-created_at')[:3]
    return render(request, 'home.html', {'latest_jobs': latest_jobs})

def about(request):
    """Render the public about page."""
    return render(request, 'about.html')
