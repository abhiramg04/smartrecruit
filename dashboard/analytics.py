"""
dashboard/analytics.py — Analytics & Reporting Data Layer for SmartRecruit.

Provides aggregated metrics and cached analytics calculations for:
- Recruiter Dashboard & Hiring Funnel
- Per-Job Analytics Breakdown
- AI Operations & Usage Analytics
- Platform-Wide Admin Reports
- Candidate Personal Statistics & Application Timeline
"""

import logging
from typing import Dict, Any, List
from django.db.models import Count, Q, Avg, FloatField, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_TIMEOUT = 120  # 2 minutes cache for aggregated stats


class AnalyticsService:
    """
    Unified analytics service providing optimized ORM aggregations
    and permission-scoped reporting data.
    """

    # ---------------------------------------------------------------------------
    # RECRUITER ANALYTICS & HIRING FUNNEL
    # ---------------------------------------------------------------------------
    @classmethod
    def get_recruiter_analytics(cls, recruiter_user, use_cache: bool = True) -> Dict[str, Any]:
        """
        Calculates recruiter-level recruitment metrics, status counts, and hiring funnel.
        Strictly restricted to recruiter_user.company.
        """
        company = getattr(recruiter_user, 'company', None)
        if not company:
            return cls._empty_recruiter_stats()

        cache_key = f"analytics_recruiter_{company.id}"
        if use_cache:
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data

        from jobs.models import Job
        from applications.models import Application
        from interviews.models import InterviewSchedule
        from assessments.models import Assessment

        # Base QuerySets scoped to recruiter's company
        jobs_qs = Job.objects.filter(company=company)
        apps_qs = Application.objects.filter(job__company=company)
        interviews_qs = InterviewSchedule.objects.filter(application__job__company=company)
        assessments_qs = Assessment.objects.filter(created_by__company=company)

        # Job Counts
        total_jobs = jobs_qs.count()
        active_jobs = jobs_qs.filter(is_published=True, is_closed=False).count()
        closed_jobs = jobs_qs.filter(is_closed=True).count()

        # Application Status Aggregations
        status_counts = apps_qs.aggregate(
            total_apps=Count('id'),
            ai_screened=Count('id', filter=Q(status__in=['AI_SCREENED', 'SCREENED', 'SHORTLISTED', 'INTERVIEW', 'HR_ROUND', 'OFFER'])),
            shortlisted=Count('id', filter=Q(status='SHORTLISTED')),
            in_interview=Count('id', filter=Q(status__in=['INTERVIEW', 'HR_ROUND'])),
            selected=Count('id', filter=Q(status='OFFER')),
            rejected=Count('id', filter=Q(status='REJECTED')),
            on_hold=Count('id', filter=Q(status='HOLD')),
        )

        total_applications = status_counts['total_apps'] or 0
        ai_screened_count = status_counts['ai_screened'] or 0
        shortlisted_count = status_counts['shortlisted'] or 0
        in_interview_count = status_counts['in_interview'] or 0
        selected_count = status_counts['selected'] or 0
        rejected_count = status_counts['rejected'] or 0

        # Interview & Assessment Counts
        scheduled_interviews = interviews_qs.filter(status='SCHEDULED').count()
        completed_interviews = interviews_qs.filter(status='COMPLETED').count()
        total_assessments = assessments_qs.count()

        # Hiring Funnel Data (Applications -> Screened -> Shortlisted -> Interviewed -> Selected)
        # Note: Screened includes all applications that passed AI screening stage or above
        screened_stage = apps_qs.filter(
            Q(status__in=['AI_SCREENED', 'SCREENED', 'SHORTLISTED', 'INTERVIEW', 'HR_ROUND', 'OFFER']) |
            Q(ai_score__isnull=False)
        ).distinct().count()

        shortlisted_stage = apps_qs.filter(
            status__in=['SHORTLISTED', 'INTERVIEW', 'HR_ROUND', 'OFFER']
        ).count()

        interviewed_stage = apps_qs.filter(
            status__in=['INTERVIEW', 'HR_ROUND', 'OFFER']
        ).count()

        selected_stage = selected_count

        funnel = [
            {'stage': 'Applied', 'count': total_applications, 'percentage': 100.0 if total_applications else 0.0},
            {'stage': 'Screened', 'count': screened_stage, 'percentage': round((screened_stage / total_applications * 100), 1) if total_applications else 0.0},
            {'stage': 'Shortlisted', 'count': shortlisted_stage, 'percentage': round((shortlisted_stage / total_applications * 100), 1) if total_applications else 0.0},
            {'stage': 'Interviewed', 'count': interviewed_stage, 'percentage': round((interviewed_stage / total_applications * 100), 1) if total_applications else 0.0},
            {'stage': 'Selected', 'count': selected_stage, 'percentage': round((selected_stage / total_applications * 100), 1) if total_applications else 0.0},
        ]

        result = {
            'total_jobs': total_jobs,
            'active_jobs': active_jobs,
            'closed_jobs': closed_jobs,
            'total_applications': total_applications,
            'ai_screened_candidates': ai_screened_count,
            'shortlisted_candidates': shortlisted_count,
            'in_interview_candidates': in_interview_count,
            'selected_candidates': selected_count,
            'rejected_candidates': rejected_count,
            'assessments_count': total_assessments,
            'scheduled_interviews': scheduled_interviews,
            'completed_interviews': completed_interviews,
            'funnel': funnel,
        }

        if use_cache:
            cache.set(cache_key, result, CACHE_TIMEOUT)

        return result

    # ---------------------------------------------------------------------------
    # JOB ANALYTICS (PER JOB BREAKDOWN)
    # ---------------------------------------------------------------------------
    @classmethod
    def get_job_analytics(cls, recruiter_user, job_id: int = None) -> List[Dict[str, Any]]:
        """
        For each recruiter job (or a specific job_id), calculates:
        - Application count
        - Screening count
        - Shortlist count
        - Interview count
        - Selection count
        - Rejection count
        - Average AI Score
        """
        company = getattr(recruiter_user, 'company', None)
        if not company and recruiter_user.role != 'ADMIN':
            return []

        from jobs.models import Job

        jobs_qs = Job.objects.all() if recruiter_user.role == 'ADMIN' else Job.objects.filter(company=company)

        if job_id:
            jobs_qs = jobs_qs.filter(id=job_id)

        jobs_qs = jobs_qs.annotate(
            app_count=Count('applications'),
            screening_count=Count('applications', filter=Q(applications__status__in=['AI_SCREENED', 'SCREENED', 'SHORTLISTED', 'INTERVIEW', 'HR_ROUND', 'OFFER']) | Q(applications__ai_score__isnull=False)),
            shortlist_count=Count('applications', filter=Q(applications__status__in=['SHORTLISTED', 'INTERVIEW', 'HR_ROUND', 'OFFER'])),
            interview_count=Count('applications', filter=Q(applications__status__in=['INTERVIEW', 'HR_ROUND', 'OFFER'])),
            selection_count=Count('applications', filter=Q(applications__status='OFFER')),
            rejection_count=Count('applications', filter=Q(applications__status='REJECTED')),
            avg_ai_score=Avg('applications__ai_score__overall_score'),
        ).order_by('-created_at')

        results = []
        for j in jobs_qs:
            results.append({
                'job_id': j.id,
                'title': j.title,
                'company_name': j.company.name if j.company else 'N/A',
                'is_active': j.is_published and not j.is_closed,
                'application_count': j.app_count,
                'screening_count': j.screening_count,
                'shortlist_count': j.shortlist_count,
                'interview_count': j.interview_count,
                'selection_count': j.selection_count,
                'rejection_count': j.rejection_count,
                'avg_ai_score': round(j.avg_ai_score, 1) if j.avg_ai_score is not None else None,
                'created_at': j.created_at,
            })

        return results

    # ---------------------------------------------------------------------------
    # AI OPERATIONAL ANALYTICS
    # ---------------------------------------------------------------------------
    @classmethod
    def get_ai_analytics(cls, recruiter_user=None, is_admin: bool = False) -> Dict[str, Any]:
        """
        Calculates operational AI usage metrics:
        - AI screening count
        - AI ranking operations
        - Interview question generation count
        - Interview analysis count
        - AI assistant usage count
        Privacy: Does not expose prompt contents.
        """
        from applications.models import ApplicationAIScore
        from ranking.models import RankingResult
        from interviews.models import InterviewSummary
        from assistant.models import ChatMessage, ChatSession
        from dashboard.models import AuditLog

        company = getattr(recruiter_user, 'company', None) if recruiter_user else None

        # Filter querysets
        if is_admin or not company:
            screening_count = ApplicationAIScore.objects.count()
            ranking_ops_count = RankingResult.objects.count()
            interview_analysis_count = InterviewSummary.objects.count()
            assistant_messages_count = ChatMessage.objects.filter(role='assistant').count()
            question_gen_count = ChatMessage.objects.filter(intent='GENERATE_QUESTIONS').count() + AuditLog.objects.filter(action__icontains='GENERATE_QUESTIONS').count()
        else:
            screening_count = ApplicationAIScore.objects.filter(application__job__company=company).count()
            ranking_ops_count = RankingResult.objects.filter(application__job__company=company).count()
            interview_analysis_count = InterviewSummary.objects.filter(application__job__company=company).count()
            assistant_messages_count = ChatMessage.objects.filter(session__user=recruiter_user, role='assistant').count()
            question_gen_count = ChatMessage.objects.filter(session__user=recruiter_user, intent='GENERATE_QUESTIONS').count()




        total_ai_ops = screening_count + ranking_ops_count + interview_analysis_count + assistant_messages_count

        return {
            'ai_screening_count': screening_count,
            'ai_ranking_ops_count': ranking_ops_count,
            'question_generation_count': question_gen_count,
            'interview_analysis_count': interview_analysis_count,
            'ai_assistant_usage_count': assistant_messages_count,
            'total_ai_operations': total_ai_ops,
        }

    # ---------------------------------------------------------------------------
    # ADMIN PLATFORM-LEVEL REPORTS
    # ---------------------------------------------------------------------------
    @classmethod
    def get_admin_analytics(cls) -> Dict[str, Any]:
        """
        Platform-wide administrator statistics across all entities.
        """
        from accounts.models import CustomUser
        from companies.models import Company
        from jobs.models import Job
        from applications.models import Application
        from interviews.models import InterviewSchedule
        from assessments.models import Assessment
        from dashboard.models import AuditLog

        total_users = CustomUser.objects.count()
        candidates_count = CustomUser.objects.filter(role='CANDIDATE').count()
        recruiters_count = CustomUser.objects.filter(role='RECRUITER').count()
        admins_count = CustomUser.objects.filter(role='ADMIN').count()
        companies_count = Company.objects.count()

        approved_companies = Company.objects.filter(is_approved=True).count()
        pending_companies = Company.objects.filter(is_approved=False).count()

        total_jobs = Job.objects.count()
        active_jobs = Job.objects.filter(is_published=True, is_closed=False).count()
        pending_jobs = Job.objects.filter(is_approved=False).count()

        total_apps = Application.objects.count()
        selected_apps = Application.objects.filter(status='OFFER').count()
        rejected_apps = Application.objects.filter(status='REJECTED').count()
        overall_selection_rate = round((selected_apps / total_apps * 100), 1) if total_apps else 0.0

        total_interviews = InterviewSchedule.objects.count()
        total_assessments = Assessment.objects.count()

        # Recent System Activity Logs
        recent_logs = list(AuditLog.objects.select_related('user').order_by('-timestamp')[:10].values(
            'id', 'action', 'description', 'timestamp', 'user__email'
        ))

        ai_stats = cls.get_ai_analytics(is_admin=True)

        return {
            'users': {
                'total': total_users,
                'candidates': candidates_count,
                'recruiters': recruiters_count,
                'companies': companies_count,
                'admins': admins_count,
            },
            'companies': {
                'approved': approved_companies,
                'pending': pending_companies,
            },
            'jobs': {
                'total': total_jobs,
                'active': active_jobs,
                'pending_approval': pending_jobs,
            },
            'applications': {
                'total': total_apps,
                'selected': selected_apps,
                'rejected': rejected_apps,
                'selection_rate': overall_selection_rate,
            },
            'interviews_total': total_interviews,
            'assessments_total': total_assessments,
            'ai_analytics': ai_stats,
            'recent_activity': recent_logs,
        }

    # ---------------------------------------------------------------------------
    # CANDIDATE PERSONAL ANALYTICS
    # ---------------------------------------------------------------------------
    @classmethod
    def get_candidate_analytics(cls, candidate_user) -> Dict[str, Any]:
        """
        Returns strictly personal statistics for a candidate.
        Recruiter & company analytics are hidden for privacy.
        """
        from applications.models import Application
        from interviews.models import InterviewSchedule
        from assessments.models import AssessmentAssignment

        profile = getattr(candidate_user, 'candidate_profile', None)
        if not profile:
            return cls._empty_candidate_stats()

        apps = Application.objects.filter(candidate=profile).select_related('job__company').order_by('-applied_at')

        total_applications = apps.count()
        shortlisted_apps = apps.filter(status__in=['SHORTLISTED', 'INTERVIEW', 'HR_ROUND', 'OFFER']).count()
        interview_count = InterviewSchedule.objects.filter(application__candidate=profile).count()
        assessment_count = AssessmentAssignment.objects.filter(application__candidate=profile).count()


        # Application Status Updates Timeline
        status_updates = []
        for app in apps[:10]:
            status_updates.append({
                'application_id': app.id,
                'job_title': app.job.title,
                'company_name': app.job.company.name if app.job.company else 'Company',
                'status': app.get_status_display(),
                'raw_status': app.status,
                'applied_at': app.applied_at,
                'updated_at': app.updated_at,
            })

        return {
            'applications_count': total_applications,
            'shortlisted_count': shortlisted_apps,
            'interviews_count': interview_count,
            'assessments_count': assessment_count,
            'status_updates': status_updates,
        }

    @staticmethod
    def _empty_recruiter_stats() -> Dict[str, Any]:
        return {
            'total_jobs': 0, 'active_jobs': 0, 'closed_jobs': 0,
            'total_applications': 0, 'ai_screened_candidates': 0,
            'shortlisted_candidates': 0, 'in_interview_candidates': 0,
            'selected_candidates': 0, 'rejected_candidates': 0,
            'assessments_count': 0, 'scheduled_interviews': 0, 'completed_interviews': 0,
            'funnel': [],
        }

    @staticmethod
    def _empty_candidate_stats() -> Dict[str, Any]:
        return {
            'applications_count': 0, 'shortlisted_count': 0,
            'interviews_count': 0, 'assessments_count': 0,
            'status_updates': [],
        }
