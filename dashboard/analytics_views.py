"""
dashboard/analytics_views.py — Views and JSON API for Phase 11 Analytics & Reporting.
"""

import logging
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View

from .analytics import AnalyticsService

logger = logging.getLogger(__name__)


class AnalyticsDashboardView(LoginRequiredMixin, TemplateView):
    """
    Role-adaptive Analytics & Reporting dashboard page.
    Role permissions:
    - CANDIDATE: Personal application statistics & status update timeline.
    - RECRUITER / COMPANY: Company recruitment metrics, hiring funnel, job analytics, AI analytics.
    - ADMIN: Platform-level statistics, company/user breakdown, AI usage, system activity log.
    """
    template_name = 'dashboard/analytics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        role = user.role

        context['user_role'] = role

        if role == 'CANDIDATE':
            context['candidate_analytics'] = AnalyticsService.get_candidate_analytics(user)
        elif role in ['RECRUITER', 'COMPANY']:
            recruiter_stats = AnalyticsService.get_recruiter_analytics(user)
            context['recruiter_analytics'] = recruiter_stats
            context['funnel'] = recruiter_stats.get('funnel', [])
            context['job_analytics'] = AnalyticsService.get_job_analytics(user)
            context['ai_analytics'] = AnalyticsService.get_ai_analytics(user)
        elif role == 'ADMIN':
            context['admin_analytics'] = AnalyticsService.get_admin_analytics()
            context['job_analytics'] = AnalyticsService.get_job_analytics(user)
            context['ai_analytics'] = AnalyticsService.get_ai_analytics(is_admin=True)

        return context


class AnalyticsDataAPIView(LoginRequiredMixin, View):
    """
    JSON API endpoint for dynamically fetching or filtering analytics data for charts.
    """
    def get(self, request, *args, **kwargs):
        user = request.user
        role = user.role

        job_id_param = request.GET.get('job_id')
        job_id = int(job_id_param) if job_id_param and job_id_param.isdigit() else None

        if role == 'CANDIDATE':
            data = AnalyticsService.get_candidate_analytics(user)
        elif role in ['RECRUITER', 'COMPANY']:
            recruiter_stats = AnalyticsService.get_recruiter_analytics(user)
            data = {
                'recruiter': recruiter_stats,
                'funnel': recruiter_stats.get('funnel', []),
                'job_analytics': AnalyticsService.get_job_analytics(user, job_id=job_id),
                'ai_analytics': AnalyticsService.get_ai_analytics(user),
            }
        elif role == 'ADMIN':
            data = {
                'admin': AnalyticsService.get_admin_analytics(),
                'job_analytics': AnalyticsService.get_job_analytics(user, job_id=job_id),
                'ai_analytics': AnalyticsService.get_ai_analytics(is_admin=True),
            }
        else:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        return JsonResponse(data)
