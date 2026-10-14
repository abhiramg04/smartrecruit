from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.views import View
from django.views.generic import DetailView, ListView

from applications.models import Application
from jobs.models import Job
from .models import RankingResult
from .engine import rank_resume


class TriggerRankingView(LoginRequiredMixin, UserPassesTestMixin, View):
    """POST endpoint to trigger AI ranking for a specific application."""

    def test_func(self):
        return self.request.user.role in ('ADMIN', 'RECRUITER', 'COMPANY')

    def post(self, request, application_pk):
        application = get_object_or_404(Application, pk=application_pk)

        try:
            candidate_profile = application.candidate
            job = application.job

            if not candidate_profile.is_parsed:
                messages.error(request, "Cannot rank: candidate has no parsed resume.")
                return redirect('ranking_dashboard', job_pk=job.pk)

            # Run the AI engine
            result_data = rank_resume(job, candidate_profile)

            if result_data.get('error'):
                messages.error(request, f"Ranking failed: {result_data['error']}")
                return redirect('ranking_dashboard', job_pk=job.pk)

            # Upsert RankingResult
            ranking, _ = RankingResult.objects.update_or_create(
                application=application,
                defaults={
                    'skill_score':       result_data['skill_score'],
                    'experience_score':  result_data['experience_score'],
                    'education_score':   result_data['education_score'],
                    'project_score':     result_data['project_score'],
                    'cert_score':        result_data['cert_score'],
                    'overall_score':     result_data['overall_score'],
                    'verdict':           result_data['verdict'],
                    'matched_skills':    result_data['matched_skills'],
                    'missing_skills':    result_data['missing_skills'],
                    'ai_recommendation': result_data['ai_recommendation'],
                    'explainability':    result_data['explainability'],
                }
            )

            messages.success(request, f"Ranking complete! Score: {ranking.overall_score:.1f}% — Verdict: {ranking.verdict}")
            return redirect('ranking_result', pk=ranking.pk)

        except Exception as e:
            messages.error(request, f"Unexpected error: {e}")
            return redirect('job_detail', pk=application.job.pk)


class RankingResultView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Detailed explainable AI result view for a single ranking."""
    model = RankingResult
    template_name = 'ranking/result.html'
    context_object_name = 'result'

    def test_func(self):
        return self.request.user.role in ('ADMIN', 'RECRUITER', 'COMPANY')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        result = self.object
        xai = result.explainability or {}
        context['component_scores'] = xai.get('component_scores', {})
        context['strengths'] = xai.get('groq_strengths', [])
        context['concerns'] = xai.get('groq_concerns', [])
        context['groq_summary'] = xai.get('groq_summary', '')
        context['groq_recommendation'] = xai.get('groq_recommendation', '')
        return context


class RankingDashboardView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Dashboard listing all ranked applications for a job, sorted by score."""
    template_name = 'ranking/dashboard.html'
    context_object_name = 'results'

    def test_func(self):
        return self.request.user.role in ('ADMIN', 'RECRUITER', 'COMPANY')

    def get_queryset(self):
        self.job = get_object_or_404(Job, pk=self.kwargs['job_pk'])
        return RankingResult.objects.filter(
            application__job=self.job
        ).select_related('application__candidate__user').order_by('-overall_score')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['job'] = self.job
        # Also show unranked applications
        ranked_app_ids = self.get_queryset().values_list('application_id', flat=True)
        context['unranked'] = Application.objects.filter(
            job=self.job
        ).exclude(id__in=ranked_app_ids)
        return context

class RecruiterCandidateListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = 'ranking/recruiter_candidate_list.html'
    context_object_name = 'results'

    def test_func(self):
        return self.request.user.role in ('ADMIN', 'RECRUITER', 'COMPANY')

    def get_queryset(self):
        user = self.request.user
        company = getattr(user, 'company', None)
        if company:
            return RankingResult.objects.filter(application__job__company=company).select_related('application__candidate__user', 'application__job').order_by('-overall_score')
        return RankingResult.objects.all().select_related('application__candidate__user', 'application__job').order_by('-overall_score')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        company = getattr(user, 'company', None)
        if company:
            context['unranked_applications'] = Application.objects.filter(job__company=company).filter(ranking_result__isnull=True).select_related('candidate__user', 'job')
        else:
            context['unranked_applications'] = Application.objects.filter(ranking_result__isnull=True).select_related('candidate__user', 'job')
        return context


