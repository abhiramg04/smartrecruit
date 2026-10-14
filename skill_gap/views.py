from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views import View
from django.views.generic import DetailView

from jobs.models import Job
from candidates.models import CandidateProfile
from .models import SkillGapReport
from .analyzer import analyze_gap


class SkillGapSelectView(LoginRequiredMixin, View):
    """Landing page: candidate selects a target job to analyze."""

    def get(self, request):
        jobs = Job.objects.filter(
            is_published=True, is_closed=False, is_approved=True
        ).select_related('company', 'category').order_by('-created_at')

        # Check if candidate has a parsed profile
        try:
            profile = request.user.candidate_profile
            has_profile = profile.is_parsed
        except CandidateProfile.DoesNotExist:
            profile = None
            has_profile = False

        # Existing reports
        existing_reports = []
        if profile:
            existing_reports = SkillGapReport.objects.filter(
                candidate=profile
            ).select_related('job').order_by('-generated_at')[:5]

        return render(request, 'skill_gap/select.html', {
            'jobs': jobs,
            'has_profile': has_profile,
            'existing_reports': existing_reports,
        })


class SkillGapAnalyzeView(LoginRequiredMixin, View):
    """POST: triggers gap analysis and stores the result."""

    def post(self, request):
        job_id = request.POST.get('job_id')
        if not job_id:
            messages.error(request, "Please select a job to analyze.")
            return redirect('skill_gap_select')

        job = get_object_or_404(Job, pk=job_id)

        try:
            profile = request.user.candidate_profile
        except CandidateProfile.DoesNotExist:
            messages.error(request, "Please upload your resume first.")
            return redirect('resume_upload')

        if not profile.is_parsed:
            messages.warning(request, "Your resume hasn't been parsed. Please re-upload it.")
            return redirect('resume_upload')

        # Run analysis
        result_data = analyze_gap(profile, job)

        if result_data.get('error'):
            messages.error(request, f"Analysis failed: {result_data['error']}")
            return redirect('skill_gap_select')

        # Upsert report
        report, created = SkillGapReport.objects.update_or_create(
            candidate=profile,
            job=job,
            defaults={
                'matched_skills':      result_data['matched_skills'],
                'missing_skills':      result_data['missing_skills'],
                'extra_skills':        result_data['extra_skills'],
                'match_percentage':    result_data['match_percentage'],
                'recommended_courses': result_data['recommended_courses'],
                'recommended_certs':   result_data['recommended_certs'],
                'learning_path':       result_data['learning_path'],
                'estimated_hours':     result_data['estimated_hours'],
                'ai_summary':          result_data['ai_summary'],
            }
        )

        action = "Generated" if created else "Updated"
        messages.success(request, f"{action} skill gap report for '{job.title}'!")
        return redirect('skill_gap_report', pk=report.pk)


class SkillGapReportView(LoginRequiredMixin, DetailView):
    """Visual dashboard showing the full skill gap report."""
    model = SkillGapReport
    template_name = 'skill_gap/report.html'
    context_object_name = 'report'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report = self.object

        # Compute weeks estimate
        weeks = max(1, report.estimated_hours // 10)
        context['weeks_estimate'] = weeks

        # Chart data for JS
        context['matched_count'] = len(report.matched_skills)
        context['missing_count'] = len(report.missing_skills)

        return context


class SkillGapPrintView(LoginRequiredMixin, DetailView):
    """Print-optimized view for PDF export."""
    model = SkillGapReport
    template_name = 'skill_gap/print.html'
    context_object_name = 'report'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['weeks_estimate'] = max(1, self.object.estimated_hours // 10)
        return context


from django.contrib.auth.mixins import UserPassesTestMixin
from django.utils import timezone
from .models import AssessmentTest, CandidateAssessment

class AssessmentListView(LoginRequiredMixin, View):
    """View assessments depending on user role."""
    def get(self, request):
        user = request.user
        if user.role == 'RECRUITER':
            company = getattr(user, 'owned_company', None) or user.company
            tests = AssessmentTest.objects.filter(job__company=company) if company else AssessmentTest.objects.none()
            assigned = CandidateAssessment.objects.filter(test__job__company=company) if company else CandidateAssessment.objects.none()
            return render(request, 'skill_gap/assessment_recruiter_list.html', {
                'tests': tests,
                'assigned_assessments': assigned
            })
        else:
            try:
                profile = user.candidate_profile
                assigned = CandidateAssessment.objects.filter(candidate=profile)
            except Exception:
                assigned = []
            return render(request, 'skill_gap/assessment_candidate_list.html', {
                'assessments': assigned
            })

class CandidateMyAssessmentsView(LoginRequiredMixin, View):
    """Candidate portal dedicated route for assessments."""
    def get(self, request):
        try:
            profile = request.user.candidate_profile
            assigned = CandidateAssessment.objects.filter(candidate=profile)
        except Exception:
            assigned = []
        return render(request, 'skill_gap/assessment_candidate_list.html', {
            'assessments': assigned
        })

class AssessmentCreateView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.role == 'RECRUITER'

    def get(self, request):
        company = getattr(request.user, 'owned_company', None) or request.user.company
        jobs = Job.objects.filter(company=company) if company else Job.objects.none()
        return render(request, 'skill_gap/assessment_form.html', {'jobs': jobs})

    def post(self, request):
        job_id = request.POST.get('job_id')
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        duration = int(request.POST.get('duration_minutes', 30))
        passing_score = float(request.POST.get('passing_score', 70.0))
        
        job = get_object_or_404(Job, pk=job_id)
        
        sample_questions = [
            {"id": 1, "question": "What is the main advantage of using RESTful APIs?", "options": ["Stateless communication", "Tightly coupled architecture", "Direct database access", "Single-threaded performance"], "correct_answer": 0},
            {"id": 2, "question": "Which HTTP method is idempotent?", "options": ["POST", "PUT", "PATCH", "CONNECT"], "correct_answer": 1},
            {"id": 3, "question": "What is the primary function of an ORM in backend engineering?", "options": ["Data visualization", "Object-relational mapping", "Network routing", "Caching"], "correct_answer": 1}
        ]

        test = AssessmentTest.objects.create(
            job=job,
            title=title,
            description=description,
            duration_minutes=duration,
            passing_score=passing_score,
            questions=sample_questions
        )
        messages.success(request, f'Assessment "{title}" created successfully!')
        return redirect('assessment_list')

class AssessmentTakeView(LoginRequiredMixin, View):
    def get(self, request, pk):
        assessment = get_object_or_404(CandidateAssessment, pk=pk, candidate__user=request.user)
        return render(request, 'skill_gap/assessment_take.html', {'assessment': assessment})

    def post(self, request, pk):
        assessment = get_object_or_404(CandidateAssessment, pk=pk, candidate__user=request.user)
        questions = assessment.test.questions
        score = 0
        total = len(questions)
        answers = {}

        for idx, q in enumerate(questions):
            ans = request.POST.get(f'q_{idx}')
            if ans is not None:
                ans_int = int(ans)
                answers[str(idx)] = ans_int
                if ans_int == q['correct_answer']:
                    score += 1

        final_score = round((score / total * 100), 1) if total > 0 else 0.0
        passed = final_score >= assessment.test.passing_score

        assessment.score = final_score
        assessment.passed = passed
        assessment.status = 'COMPLETED'
        assessment.answers = answers
        assessment.completed_at = timezone.now()
        assessment.save()

        messages.success(request, f"Assessment completed! Your score: {final_score}% ({'Passed' if passed else 'Needs Improvement'})")
        return redirect('my_assessments')

