from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.views import View
from django.views.generic import ListView

from jobs.models import Job
from candidates.models import CandidateProfile
from .models import Application, ApplicationAIScore


class ApplyView(LoginRequiredMixin, View):
    """Allow a Candidate to apply to a Job. Triggers AI screening on new applications."""

    def post(self, request, job_pk):
        job = get_object_or_404(Job, pk=job_pk, is_published=True, is_closed=False)

        try:
            profile = request.user.candidate_profile
        except CandidateProfile.DoesNotExist:
            messages.error(request, "Please upload your resume before applying.")
            return redirect('resume_upload')

        if not profile.is_parsed:
            messages.warning(request, "Your resume hasn't been parsed yet. Please re-upload it.")
            return redirect('resume_upload')

        cover_letter = request.POST.get('cover_letter', '').strip()

        application, created = Application.objects.get_or_create(
            candidate=profile,
            job=job,
            defaults={'cover_letter': cover_letter}
        )

        if created:
            # ── Phase 07: Trigger AI screening & ranking ──────────────────
            self._run_ai_screening(application, job, profile)
            # ── Phase 09: Notify candidate + recruiters ───────────────────
            try:
                from dashboard.services.notification_service import NotificationService
                NotificationService.notify_application_submitted(application)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Notification dispatch failed: {e}")
            messages.success(request, f"Successfully applied to '{job.title}'! Good luck!")
        else:
            messages.info(request, f"You've already applied to '{job.title}'.")

        return redirect('job_detail', pk=job_pk)

    # ── AI screening helper ───────────────────────────────────────────────────

    @staticmethod
    def _run_ai_screening(application: Application, job: Job, profile: CandidateProfile):
        """
        Invoke the Phase 07 AI ranking pipeline and persist the result in
        ApplicationAIScore.  Errors are caught so the application is never lost.
        """
        try:
            from core.ai.manager import ai_manager
            from dashboard.models import AIConfiguration
            cfg = AIConfiguration.get_solo()
            if not cfg.enable_ai_ranking:
                return

            # Build candidate data dict
            candidate_data = {
                'skills':          profile.skills or [],
                'experience':      profile.experience_structured,
                'education':       profile.education_structured,
                'projects':        profile.projects_structured,
                'certifications':  profile.certifications or [],
                'raw_text':        profile.raw_text or '',
            }

            job_skills = list(job.skills.values_list('name', flat=True))

            ranking = ai_manager.rank_candidate(
                job_title       = job.title,
                job_description = job.description,
                job_skills      = job_skills,
                candidate_data  = candidate_data,
            )

            ApplicationAIScore.objects.update_or_create(
                application=application,
                defaults={
                    'overall_score':       ranking['overall_score'],
                    'skill_score':         ranking['skill_score'],
                    'experience_score':    ranking['experience_score'],
                    'education_score':     ranking['education_score'],
                    'semantic_score':      ranking['semantic_score'],
                    'ai_evaluation_score': ranking['ai_evaluation_score'],
                    'ai_recommendation':   ranking['ai_recommendation'],
                    'ai_strengths':        ranking['ai_strengths'],
                    'ai_missing_skills':   ranking['ai_missing_skills'],
                    'ai_rationale':        ranking['ai_rationale'],
                },
            )

            # Also generate & persist the candidate's resume embedding
            ai_manager.generate_and_store_resume_embedding(profile)

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(
                f"AI screening failed for application {application.pk}: {e}", exc_info=True
            )



class MyApplicationsView(LoginRequiredMixin, ListView):
    """Candidate's personal applications dashboard."""
    template_name = 'applications/my_applications.html'
    context_object_name = 'applications'

    def get_queryset(self):
        try:
            profile = self.request.user.candidate_profile
            return Application.objects.filter(candidate=profile).select_related(
                'job', 'job__company'
            ).prefetch_related('ranking_result')
        except CandidateProfile.DoesNotExist:
            return Application.objects.none()

class ManageApplicationsView(LoginRequiredMixin, ListView):
    """Company/Recruiter dashboard to view all applications for their jobs — Phase 07 AI Ranking."""
    template_name = 'applications/manage_list.html'
    context_object_name = 'applications'
    paginate_by = 20

    def test_func(self):
        return self.request.user.role in ['COMPANY', 'RECRUITER']

    def get_queryset(self):
        user = self.request.user
        company = None
        if user.role == 'COMPANY' and hasattr(user, 'owned_company'):
            company = user.owned_company
        elif user.role == 'RECRUITER' and hasattr(user, 'company'):
            company = user.company

        if not company:
            return Application.objects.none()

        qs = Application.objects.filter(job__company=company).select_related(
            'candidate', 'candidate__user', 'job'
        ).prefetch_related('ai_score')

        # Filters
        status = self.request.GET.get('status')
        job_id = self.request.GET.get('job_id')
        q      = self.request.GET.get('q')

        if status:
            qs = qs.filter(status=status)
        if job_id:
            qs = qs.filter(job_id=job_id)
        if q:
            from django.db.models import Q as DQ
            qs = qs.filter(
                DQ(candidate__user__first_name__icontains=q) |
                DQ(candidate__user__last_name__icontains=q)  |
                DQ(candidate__user__username__icontains=q)   |
                DQ(candidate__user__email__icontains=q)      |
                DQ(job__title__icontains=q)
            )

        # When filtered by job: order by AI overall_score DESC (AI ranking).
        # Otherwise order by application date.
        if job_id:
            from django.db.models import FloatField, Value
            from django.db.models.functions import Coalesce
            qs = qs.annotate(
                ai_rank=Coalesce('ai_score__overall_score', Value(0.0, output_field=FloatField()))
            ).order_by('-ai_rank', '-applied_at')
        else:
            qs = qs.order_by('-applied_at')

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        company = None
        if user.role == 'COMPANY' and hasattr(user, 'owned_company'):
            company = user.owned_company
        elif user.role == 'RECRUITER' and hasattr(user, 'company'):
            company = user.company

        if company:
            context['company_jobs'] = Job.objects.filter(company=company)
        # Flag to tell the template that ranking info is available
        context['show_ai_ranking'] = bool(self.request.GET.get('job_id'))
        return context


from django.views.generic import DetailView
from django.utils import timezone

class ApplicationDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View to see full timeline and logs of an application."""
    model = Application
    template_name = 'applications/workflow_dashboard.html'
    context_object_name = 'application'
    
    def test_func(self):
        # Recruiter, Admin or the Candidate themselves can view
        app = self.get_object()
        user = self.request.user
        return user.role in ('ADMIN', 'RECRUITER', 'COMPANY') or app.candidate.user == user

class WorkflowUpdateView(LoginRequiredMixin, View):
    """Handle status update POST request — delegates to WorkflowEngine."""
    def post(self, request, pk):
        if request.user.role not in ('ADMIN', 'RECRUITER', 'COMPANY'):
            messages.error(request, "Permission denied.")
            return redirect('dashboard')

        application = get_object_or_404(Application, pk=pk)
        new_status = request.POST.get('status')
        notes = request.POST.get('notes', '').strip()

        if new_status and new_status in dict(Application.STATUS_CHOICES):
            from core.services.workflow import WorkflowEngine, WorkflowError
            engine = WorkflowEngine(application)
            try:
                engine._do_transition(new_status, notes, recruiter_user=request.user)
                messages.success(request, f"Status updated to {dict(Application.STATUS_CHOICES)[new_status]}.")
            except WorkflowError as e:
                messages.error(request, f"Workflow error: {e}")
        else:
            messages.error(request, "Invalid status selected.")

        next_url = request.POST.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('application_workflow', pk=application.pk)

class ApplicationQuickActionView(LoginRequiredMixin, View):
    """Recruiter quick actions: SHORTLIST, HOLD, REJECT — delegates to WorkflowEngine."""
    def post(self, request, pk, action):
        if request.user.role not in ('ADMIN', 'RECRUITER', 'COMPANY'):
            messages.error(request, "Permission denied.")
            return redirect('manage_applications')

        application = get_object_or_404(Application, pk=pk)
        action_upper = action.upper()
        notes = request.POST.get('notes', '').strip()

        from core.services.workflow import WorkflowEngine, WorkflowError
        engine = WorkflowEngine(application)

        try:
            if action_upper == 'SHORTLIST':
                engine.shortlist_candidate(request.user, notes)
            elif action_upper == 'HOLD':
                engine.hold_candidate(request.user, notes)
            elif action_upper == 'REJECT':
                engine.reject_candidate(request.user, notes)
            else:
                messages.error(request, "Invalid action.")
                return redirect('manage_applications')
            messages.success(request, f"Action '{action_upper}' applied successfully.")
        except WorkflowError as e:
            messages.error(request, f"Workflow error: {e}")

        return redirect('manage_applications')

class HiringDecisionView(LoginRequiredMixin, View):
    """Recruiter final hiring decision view (SELECT, REJECT, HOLD)."""
    def get(self, request, pk):
        if request.user.role not in ('ADMIN', 'RECRUITER', 'COMPANY'):
            messages.error(request, "Permission denied.")
            return redirect('manage_applications')

        application = get_object_or_404(Application, pk=pk)
        ranking_result = getattr(application, 'ranking_result', None)
        assessment_results = application.assessment_results.all()
        interview_schedules = application.interview_schedules.all()
        interview_summary = getattr(application, 'interview_summary', None)

        return render(request, 'applications/hiring_decision.html', {
            'application': application,
            'ranking_result': ranking_result,
            'assessment_results': assessment_results,
            'interview_schedules': interview_schedules,
            'interview_summary': interview_summary,
        })

    def post(self, request, pk):
        if request.user.role not in ('ADMIN', 'RECRUITER', 'COMPANY'):
            messages.error(request, "Permission denied.")
            return redirect('manage_applications')

        application = get_object_or_404(Application, pk=pk)
        decision = request.POST.get('decision', '').upper()
        notes = request.POST.get('notes', '').strip()

        if decision not in ['SELECT', 'REJECT', 'HOLD']:
            messages.error(request, "Invalid decision selected.")
            return redirect('hiring_decision', pk=pk)

        from core.services.workflow import WorkflowEngine, WorkflowError
        engine = WorkflowEngine(application)
        try:
            engine.make_hiring_decision(request.user, decision, notes)
            messages.success(request, f"Final decision '{decision}' recorded for {application.candidate.user.get_full_name()}.")
        except WorkflowError as e:
            messages.error(request, f"Workflow error: {e}")
            return redirect('hiring_decision', pk=pk)

        return redirect('manage_applications')

