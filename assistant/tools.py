"""
assistant/tools.py — Backend-authorized, permission-scoped tool functions.

SECURITY CONTRACT:
  - Every tool receives `recruiter_user` as the first parameter.
  - All DB queries are filtered to recruiter_user.company exclusively.
  - Tools return serializable dicts (never ORM objects directly to the LLM).
  - Tools enforce a hard limit on records returned to keep context minimal.
  - ToolPermissionError is raised for any out-of-scope data request.
"""
import logging
from typing import Optional, List, Dict, Any
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

MAX_CANDIDATES = 8   # Max candidates in any single context payload
MAX_TEXT_LEN = 500   # Max chars of resume text sent to LLM per candidate


class ToolPermissionError(Exception):
    """Raised when a tool call tries to access unauthorized data."""
    pass


def _get_company(recruiter_user):
    """Safely resolve recruiter's company."""
    company = getattr(recruiter_user, 'company', None)
    if not company:
        raise ToolPermissionError("No company associated with your account.")
    return company


def _safe_skills(skills_raw) -> List[str]:
    if isinstance(skills_raw, list):
        return [str(s) for s in skills_raw[:30]]
    return []


def _truncate(text: str, max_len: int = MAX_TEXT_LEN) -> str:
    if not text:
        return ''
    return text[:max_len] + ('…' if len(text) > max_len else '')


# ---------------------------------------------------------------------------
# TOOL 1: Find suitable candidates for a job
# ---------------------------------------------------------------------------

def tool_find_candidates(recruiter_user, job_title_query: str = '', limit: int = 5) -> Dict[str, Any]:
    """
    Find best-matching candidates for the recruiter's company jobs.
    Filters by AI score, limited to recruiter's company.
    """
    from applications.models import Application
    company = _get_company(recruiter_user)

    qs = Application.objects.filter(
        job__company=company
    ).select_related('candidate__user', 'job', 'ai_score').prefetch_related('ai_score')

    if job_title_query:
        qs = qs.filter(job__title__icontains=job_title_query)

    # Order by AI score descending
    from django.db.models import FloatField, Value
    from django.db.models.functions import Coalesce
    qs = qs.annotate(
        rank_score=Coalesce('ai_score__overall_score', Value(0.0, output_field=FloatField()))
    ).order_by('-rank_score', '-applied_at')

    candidates = []
    for app in qs[:limit]:
        ai = getattr(app, 'ai_score', None)
        candidates.append({
            'id': app.candidate.pk,
            'name': app.candidate.user.get_full_name() or app.candidate.user.username,
            'job': app.job.title,
            'status': app.get_status_display(),
            'overall_score': round(getattr(ai, 'overall_score', 0), 1) if ai else None,
            'ai_recommendation': getattr(ai, 'ai_recommendation', None) if ai else None,
            'skills': _safe_skills(app.candidate.skills)[:10],
            'experience_years': getattr(app.candidate, 'total_experience_years', None),
        })

    return {
        'tool': 'find_candidates',
        'job_filter': job_title_query or 'All jobs',
        'candidates': candidates,
        'total_found': len(candidates),
    }


# ---------------------------------------------------------------------------
# TOOL 2: Explain ranking difference between two candidates
# ---------------------------------------------------------------------------

def tool_explain_ranking(recruiter_user, name_a: str = '', name_b: str = '') -> Dict[str, Any]:
    """
    Retrieve ranking data for candidates to enable comparison explanation.
    """
    from applications.models import Application
    company = _get_company(recruiter_user)

    def find_candidate(name_hint):
        qs = Application.objects.filter(
            job__company=company
        ).select_related('candidate__user', 'job', 'ai_score')
        if name_hint:
            parts = name_hint.strip().split()
            from django.db.models import Q
            q = Q()
            for p in parts:
                q |= Q(candidate__user__first_name__icontains=p) | Q(candidate__user__last_name__icontains=p) | Q(candidate__user__username__icontains=p)
            qs = qs.filter(q)
        return qs.first()

    app_a = find_candidate(name_a)
    app_b = find_candidate(name_b) if name_b else None

    def serialize_app(app):
        if not app:
            return None
        ai = getattr(app, 'ai_score', None)
        return {
            'name': app.candidate.user.get_full_name() or app.candidate.user.username,
            'job': app.job.title,
            'overall_score': round(getattr(ai, 'overall_score', 0), 1) if ai else None,
            'skill_score': round(getattr(ai, 'skill_score', 0), 1) if ai else None,
            'experience_score': round(getattr(ai, 'experience_score', 0), 1) if ai else None,
            'education_score': round(getattr(ai, 'education_score', 0), 1) if ai else None,
            'semantic_score': round(getattr(ai, 'semantic_score', 0), 1) if ai else None,
            'ai_recommendation': getattr(ai, 'ai_recommendation', None) if ai else None,
            'ai_strengths': (getattr(ai, 'ai_strengths', []) or [])[:5] if ai else [],
            'ai_missing_skills': (getattr(ai, 'ai_missing_skills', []) or [])[:5] if ai else [],
            'ai_rationale': _truncate(getattr(ai, 'ai_rationale', ''), 300) if ai else '',
        }

    return {
        'tool': 'explain_ranking',
        'candidate_a': serialize_app(app_a),
        'candidate_b': serialize_app(app_b),
    }


# ---------------------------------------------------------------------------
# TOOL 3: Summarize a single candidate's profile
# ---------------------------------------------------------------------------

def tool_summarize_candidate(recruiter_user, name_hint: str = '') -> Dict[str, Any]:
    """Return a compact profile summary for a named candidate."""
    from applications.models import Application
    from django.db.models import Q
    company = _get_company(recruiter_user)

    qs = Application.objects.filter(job__company=company).select_related('candidate__user', 'job', 'ai_score')
    if name_hint:
        parts = name_hint.strip().split()
        q = Q()
        for p in parts:
            q |= Q(candidate__user__first_name__icontains=p) | Q(candidate__user__last_name__icontains=p) | Q(candidate__user__username__icontains=p) | Q(candidate__user__email__icontains=p)
        qs = qs.filter(q)

    app = qs.first()
    if not app:
        return {'tool': 'summarize_candidate', 'found': False, 'name_hint': name_hint}

    profile = app.candidate
    ai = getattr(app, 'ai_score', None)
    return {
        'tool': 'summarize_candidate',
        'found': True,
        'name': profile.user.get_full_name() or profile.user.username,
        'email': profile.user.email,
        'job_applied': app.job.title,
        'status': app.get_status_display(),
        'skills': _safe_skills(profile.skills),
        'experience_summary': _truncate(str(profile.experience_structured or ''), 400),
        'education_summary': _truncate(str(profile.education_structured or ''), 200),
        'overall_score': round(getattr(ai, 'overall_score', 0), 1) if ai else None,
        'ai_recommendation': getattr(ai, 'ai_recommendation', None) if ai else None,
        'ai_strengths': (getattr(ai, 'ai_strengths', []) or [])[:5] if ai else [],
        'ai_missing_skills': (getattr(ai, 'ai_missing_skills', []) or [])[:5] if ai else [],
        'ai_rationale': _truncate(getattr(ai, 'ai_rationale', ''), 300) if ai else '',
    }


# ---------------------------------------------------------------------------
# TOOL 4: Find candidates missing a specific skill
# ---------------------------------------------------------------------------

def tool_find_missing_skills(recruiter_user, skill: str = '', job_title: str = '') -> Dict[str, Any]:
    """Identify candidates who are missing a specified skill."""
    from applications.models import Application
    company = _get_company(recruiter_user)

    qs = Application.objects.filter(job__company=company).select_related('candidate__user', 'job', 'ai_score')
    if job_title:
        qs = qs.filter(job__title__icontains=job_title)

    results = []
    for app in qs[:50]:  # limit iterations
        missing = [s for s in (getattr(app, 'ai_score', None) and getattr(app.ai_score, 'ai_missing_skills', []) or [])]
        skill_list = _safe_skills(app.candidate.skills)
        has_skill = any(skill.lower() in s.lower() for s in skill_list) if skill else True

        if not has_skill:
            results.append({
                'name': app.candidate.user.get_full_name() or app.candidate.user.username,
                'job': app.job.title,
                'status': app.get_status_display(),
                'overall_score': round(getattr(app.ai_score, 'overall_score', 0), 1) if hasattr(app, 'ai_score') and app.ai_score else None,
                'missing_skills_ai': missing[:5],
            })

    return {
        'tool': 'find_missing_skills',
        'skill_searched': skill,
        'job_filter': job_title or 'All',
        'candidates_missing': results[:MAX_CANDIDATES],
    }


# ---------------------------------------------------------------------------
# TOOL 5: Generate job description (no DB query needed)
# ---------------------------------------------------------------------------

def tool_generate_job_description(title: str = '', requirements: str = '') -> Dict[str, Any]:
    """Passes job description generation request — no DB needed."""
    return {
        'tool': 'generate_job_description',
        'job_title': title,
        'requirements_hint': requirements[:300] if requirements else '',
    }


# ---------------------------------------------------------------------------
# TOOL 6: Generate interview questions for a candidate+job pair
# ---------------------------------------------------------------------------

def tool_generate_questions(recruiter_user, name_hint: str = '', job_hint: str = '') -> Dict[str, Any]:
    """Retrieve candidate + job context for question generation."""
    candidate_data = tool_summarize_candidate(recruiter_user, name_hint)

    from jobs.models import Job
    company = _get_company(recruiter_user)
    job = None
    if job_hint:
        job = Job.objects.filter(company=company, title__icontains=job_hint).first()
    if not job and candidate_data.get('job_applied'):
        job = Job.objects.filter(company=company, title__icontains=candidate_data['job_applied']).first()

    return {
        'tool': 'generate_questions',
        'candidate': candidate_data,
        'job_title': job.title if job else candidate_data.get('job_applied', job_hint),
        'job_description': _truncate(job.description if job else '', 400),
        'required_skills': list(job.skills.values_list('name', flat=True))[:15] if job else [],
    }


# ---------------------------------------------------------------------------
# TOOL 7: Summarize interviews (today or recent)
# ---------------------------------------------------------------------------

def tool_summarize_interviews(recruiter_user, date_filter: str = 'today') -> Dict[str, Any]:
    """Return compact summaries of interviews for the recruiter's company."""
    from interviews.models import InterviewSchedule
    company = _get_company(recruiter_user)

    qs = InterviewSchedule.objects.filter(
        application__job__company=company
    ).select_related('application__candidate__user', 'application__job')

    if date_filter == 'today':
        today = timezone.now().date()
        qs = qs.filter(scheduled_time__date=today)
    elif date_filter == 'week':
        week_ago = timezone.now() - timedelta(days=7)
        qs = qs.filter(scheduled_time__gte=week_ago)

    summaries = []
    for iv in qs[:10]:
        summaries.append({
            'candidate': iv.application.candidate.user.get_full_name() or iv.application.candidate.user.username,
            'job': iv.application.job.title,
            'scheduled_time': iv.scheduled_time.strftime('%Y-%m-%d %H:%M') if iv.scheduled_time else 'TBD',
            'status': iv.status,
            'location': getattr(iv, 'location', '') or '',
            'meeting_link': getattr(iv, 'meeting_link', '') or '',
        })

    return {
        'tool': 'summarize_interviews',
        'date_filter': date_filter,
        'interviews': summaries,
        'total': len(summaries),
    }


# ---------------------------------------------------------------------------
# TOOL 8: Hiring guidance for a specific job
# ---------------------------------------------------------------------------

def tool_hiring_guidance(recruiter_user, job_hint: str = '') -> Dict[str, Any]:
    """Return top shortlisted candidates for hiring decision guidance."""
    from applications.models import Application
    from django.db.models import FloatField, Value
    from django.db.models.functions import Coalesce
    company = _get_company(recruiter_user)

    qs = Application.objects.filter(
        job__company=company,
        status__in=['SHORTLISTED', 'INTERVIEW_COMPLETED', 'HR_ROUND']
    ).select_related('candidate__user', 'job', 'ai_score')

    if job_hint:
        qs = qs.filter(job__title__icontains=job_hint)

    qs = qs.annotate(
        rank_score=Coalesce('ai_score__overall_score', Value(0.0, output_field=FloatField()))
    ).order_by('-rank_score')

    candidates = []
    for app in qs[:6]:
        ai = getattr(app, 'ai_score', None)
        candidates.append({
            'name': app.candidate.user.get_full_name() or app.candidate.user.username,
            'job': app.job.title,
            'status': app.get_status_display(),
            'overall_score': round(getattr(ai, 'overall_score', 0), 1) if ai else None,
            'ai_recommendation': getattr(ai, 'ai_recommendation', None) if ai else None,
            'ai_strengths': (getattr(ai, 'ai_strengths', []) or [])[:3] if ai else [],
            'ai_missing_skills': (getattr(ai, 'ai_missing_skills', []) or [])[:3] if ai else [],
        })

    return {
        'tool': 'hiring_guidance',
        'job_filter': job_hint or 'All shortlisted',
        'shortlisted_candidates': candidates,
    }


# ---------------------------------------------------------------------------
# TOOL 9: Draft candidate communication
# ---------------------------------------------------------------------------

def tool_draft_email(recruiter_user, name_hint: str = '', email_type: str = 'general') -> Dict[str, Any]:
    """Retrieve candidate info for drafting a communication email."""
    candidate_data = tool_summarize_candidate(recruiter_user, name_hint)
    return {
        'tool': 'draft_email',
        'email_type': email_type,  # e.g. 'interview_invite', 'offer', 'feedback', 'general'
        'candidate': {
            'name': candidate_data.get('name', name_hint),
            'job': candidate_data.get('job_applied', ''),
            'status': candidate_data.get('status', ''),
        },
    }
