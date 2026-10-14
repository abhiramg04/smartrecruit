import os
import json
import logging
from django.views.generic import TemplateView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views import View
from django.http import JsonResponse
from django.db.models import Q

from .models import CandidateProfile
from .forms import ResumeUploadForm, CandidateProfileForm
from .parser import parse_resume

logger = logging.getLogger(__name__)


class ResumeUploadView(LoginRequiredMixin, View):
    """
    Handles resume file uploads and triggers the parsing engine.
    Responds with JSON for AJAX-based progress loader support.
    """

    def get(self, request):
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        form = ResumeUploadForm(instance=profile)
        return self._render(request, form, profile)

    def post(self, request):
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        form = ResumeUploadForm(request.POST, request.FILES, instance=profile)

        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if form.is_valid():
            profile = form.save(commit=False)
            profile.is_parsed = False
            profile.parse_error = None
            profile.save()

            try:
                file_path = profile.resume_file.path
                extension = os.path.splitext(profile.resume_file.name)[1]
                parsed = parse_resume(file_path, extension)

                if parsed.get('error'):
                    profile.parse_error = parsed['error']
                    profile.is_parsed = False
                else:
                    profile.full_name = parsed.get('full_name') or ''
                    profile.email = parsed.get('email') or ''
                    profile.phone = parsed.get('phone') or ''
                    profile.summary = parsed.get('summary') or ''
                    profile.linkedin_url = parsed.get('linkedin_url') or ''
                    profile.github_url = parsed.get('github_url') or ''
                    profile.skills = parsed.get('skills', [])
                    profile.education = parsed.get('education', [])
                    profile.experience = parsed.get('experience', [])
                    profile.projects = parsed.get('projects', [])
                    profile.certifications = parsed.get('certifications', [])
                    profile.languages = parsed.get('languages', [])
                    profile.raw_text = parsed.get('raw_text', '')
                    profile.is_parsed = True

                profile.save()

                if is_ajax:
                    return JsonResponse({
                        'status': 'success',
                        'redirect': '/candidates/profile/'
                    })

                messages.success(request, 'Resume parsed successfully! Your profile has been generated.')
                return redirect('candidate_profile')

            except Exception as e:
                profile.parse_error = str(e)
                profile.save()
                error_msg = f"Parsing failed: {e}"

                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': error_msg}, status=400)

                messages.error(request, error_msg)
        else:
            if is_ajax:
                errors = form.errors.as_json()
                return JsonResponse({'status': 'error', 'message': json.loads(errors)}, status=400)

        return self._render(request, form, profile)

    def _render(self, request, form, profile):
        return render(request, 'candidates/upload.html', {
            'form': form,
            'profile': profile,
        })


class CandidateProfileView(LoginRequiredMixin, TemplateView):
    """Display the generated candidate profile from parsed resume data."""
    template_name = 'candidates/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, _ = CandidateProfile.objects.get_or_create(user=self.request.user)

        # Force re-parse if requested via query param or if sections are missing
        reparse = self.request.GET.get('reparse') == 'true'
        should_auto_reparse = reparse or (
            profile.resume_file and
            os.path.exists(profile.resume_file.path) and
            (not profile.experience and not profile.education and not profile.projects)
        )

        if should_auto_reparse:
            try:
                file_path = profile.resume_file.path
                extension = os.path.splitext(profile.resume_file.name)[1]
                parsed = parse_resume(file_path, extension)

                if not parsed.get('error'):
                    profile.full_name = parsed.get('full_name') or profile.full_name or ''
                    profile.email = parsed.get('email') or profile.email or ''
                    profile.phone = parsed.get('phone') or profile.phone or ''
                    profile.summary = parsed.get('summary') or profile.summary or ''
                    profile.linkedin_url = parsed.get('linkedin_url') or profile.linkedin_url or ''
                    profile.github_url = parsed.get('github_url') or profile.github_url or ''
                    profile.skills = parsed.get('skills', [])
                    profile.education = parsed.get('education', [])
                    profile.experience = parsed.get('experience', [])
                    profile.projects = parsed.get('projects', [])
                    profile.certifications = parsed.get('certifications', [])
                    profile.languages = parsed.get('languages', [])
                    profile.raw_text = parsed.get('raw_text', '')
                    profile.is_parsed = True
                    profile.parse_error = None
                    profile.save()
            except Exception as e:
                logger.error(f"Auto re-parsing failed: {e}")

        context['profile'] = profile
        return context


class CandidateProfileEditView(LoginRequiredMixin, View):
    """Allow Candidate to manually edit profile information."""
    template_name = 'candidates/profile_edit.html'

    def get(self, request):
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        form = CandidateProfileForm(instance=profile)
        return render(request, self.template_name, {'form': form, 'profile': profile})

    def post(self, request):
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        form = CandidateProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            # Update CustomUser first_name and last_name if provided
            full_name = form.cleaned_data.get('full_name', '').strip()
            if full_name:
                parts = full_name.split(' ', 1)
                request.user.first_name = parts[0]
                request.user.last_name = parts[1] if len(parts) > 1 else ''
                request.user.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('candidate_profile')
        return render(request, self.template_name, {'form': form, 'profile': profile})


class RecruiterCandidateListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Recruiter/Admin view: Browse all parsed candidate profiles."""
    model = CandidateProfile
    template_name = 'candidates/recruiter_list.html'
    context_object_name = 'candidates'
    paginate_by = 12

    def test_func(self):
        return self.request.user.role in ('ADMIN', 'RECRUITER', 'COMPANY')

    def get_queryset(self):
        qs = CandidateProfile.objects.filter(is_parsed=True).select_related('user')
        q = self.request.GET.get('q', '').strip()
        skill = self.request.GET.get('skill', '').strip()
        if q:
            qs = qs.filter(
                Q(full_name__icontains=q) |
                Q(user__email__icontains=q) |
                Q(user__username__icontains=q)
            )
        if skill:
            # skills is a JSONField list of strings
            qs = qs.filter(skills__icontains=skill)
        return qs.order_by('-uploaded_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '')
        context['skill'] = self.request.GET.get('skill', '')
        return context


class RecruiterCandidateDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Recruiter/Admin view: Full candidate profile with resume & application history."""
    model = CandidateProfile
    template_name = 'candidates/recruiter_detail.html'
    context_object_name = 'profile'

    def test_func(self):
        return self.request.user.role in ('ADMIN', 'RECRUITER', 'COMPANY')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.get_object()
        context['applications'] = profile.applications.select_related(
            'job', 'job__company'
        ).order_by('-applied_at')
        return context


from django.http import FileResponse, Http404

class ResumeDeleteView(LoginRequiredMixin, View):
    """Delete candidate resume securely."""
    def post(self, request, *args, **kwargs):
        try:
            profile = CandidateProfile.objects.get(user=request.user)
            if profile.resume_file:
                try:
                    profile.resume_file.delete(save=False)
                except Exception:
                    pass
                profile.resume_file = None
                profile.is_parsed = False
                profile.save()
                messages.success(request, "Resume deleted successfully.")
        except CandidateProfile.DoesNotExist:
            pass
        return redirect('resume_upload')


class SecureResumeDownloadView(LoginRequiredMixin, View):
    """Serve candidate resume file through a secure authorized endpoint."""
    def get(self, request, pk, *args, **kwargs):
        profile = get_object_or_404(CandidateProfile, pk=pk)
        
        # Check permissions: candidate owner, recruiter, or admin
        user = request.user
        is_owner = (profile.user == user)
        is_staff = user.role in ('ADMIN', 'RECRUITER')
        
        if not (is_owner or is_staff):
            messages.error(request, "Unauthorized document access.")
            return redirect('login')
            
        if not profile.resume_file or not os.path.exists(profile.resume_file.path):
            raise Http404("Resume file not found.")
            
        return FileResponse(open(profile.resume_file.path, 'rb'), content_type='application/pdf')

