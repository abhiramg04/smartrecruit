"""
Interview views — Phase 08.

Module 5 — Interview Question Generator:
  GenerateQuestionsView       GET  config form / POST  generate + store
  QuestionSetDetailView       GET  categorized question bank
  EditQuestionView            POST inline edit a single InterviewQuestion
  DeleteQuestionView          POST delete a single InterviewQuestion

Module 7 — Interview Intelligence:
  UploadTranscriptView        GET/POST  audio upload OR text paste → STT → AI analysis
  InterviewSummaryDetailView  GET recruiter intelligence panel
  ExportSummaryPDFView        GET PDF export

Interview Scheduling (unchanged from Phase 04):
  InterviewScheduleCreateView
  ScheduledInterviewsListView
  InterviewStatusUpdateView
  CandidateInterviewsListView
"""

import json
import logging
import os

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.views.generic import DetailView, ListView
from django.utils.dateparse import parse_datetime

from applications.models import Application
from dashboard.models import Notification
from .models import (
    InterviewQuestionSet, InterviewQuestion,
    InterviewSummary, InterviewSchedule,
    CATEGORY_CHOICES, DIFFICULTY_CHOICES, EXPERIENCE_CHOICES,
)
from .engine import (
    generate_interview_questions,
    transcribe_audio_with_groq,
    generate_interview_intelligence,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Recruiter guard mixin
# ─────────────────────────────────────────────────────────────────────────────
class RecruiterRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.role in ('ADMIN', 'RECRUITER', 'COMPANY')


# ─────────────────────────────────────────────────────────────────────────────
# Module 5 — Interview Question Generator
# ─────────────────────────────────────────────────────────────────────────────

class GenerateQuestionsView(RecruiterRequiredMixin, View):
    """
    GET  → Show config form (difficulty, count, categories, experience).
    POST → Generate questions via Groq, store InterviewQuestion rows, redirect to detail.
    """

    CATEGORY_CODES = [code for code, _ in CATEGORY_CHOICES]

    def get(self, request, application_pk):
        application = get_object_or_404(Application, pk=application_pk)
        # Pre-fill from existing question set if available
        existing = getattr(application, 'interview_questions', None)
        context = {
            'application':       application,
            'category_choices':  CATEGORY_CHOICES,
            'difficulty_choices': DIFFICULTY_CHOICES,
            'experience_choices': EXPERIENCE_CHOICES,
            'existing':          existing,
        }
        return render(request, 'interviews/generate_form.html', context)

    def post(self, request, application_pk):
        application = get_object_or_404(Application, pk=application_pk)

        difficulty       = request.POST.get('difficulty', 'MEDIUM')
        num_questions    = int(request.POST.get('num_questions', 15))
        experience_level = request.POST.get('experience_level', 'MID')
        categories       = request.POST.getlist('categories') or ['TECHNICAL', 'BEHAVIORAL', 'HR']

        num_questions = max(5, min(num_questions, 40))

        q_set = generate_interview_questions(
            application      = application,
            difficulty       = difficulty,
            num_questions    = num_questions,
            experience_level = experience_level,
            selected_categories = categories,
        )

        if not q_set:
            messages.error(request, "Failed to generate interview questions. Please try again.")
            return redirect('generate_interview_questions', application_pk=application_pk)

        count = q_set.interview_questions.count()
        messages.success(request, f"Successfully generated {count} interview questions!")
        return redirect('interview_questions_detail', pk=q_set.pk)


class QuestionSetDetailView(RecruiterRequiredMixin, DetailView):
    """Display generated question bank with category tabs, difficulty badges, and inline edit."""
    model = InterviewQuestionSet
    template_name = 'interviews/detail.html'
    context_object_name = 'question_set'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.object
        # Group questions by category
        categories = {}
        for code, label in CATEGORY_CHOICES:
            qs_filtered = qs.interview_questions.filter(category=code)
            if qs_filtered.exists():
                categories[label] = qs_filtered
        context['categories'] = categories
        context['category_choices'] = CATEGORY_CHOICES
        context['difficulty_choices'] = DIFFICULTY_CHOICES
        context['total_count'] = qs.interview_questions.count()
        return context


class EditQuestionView(RecruiterRequiredMixin, View):
    """Inline edit a single InterviewQuestion (AJAX-friendly POST)."""

    def post(self, request, pk):
        question = get_object_or_404(InterviewQuestion, pk=pk)
        try:
            body = json.loads(request.body.decode())
        except Exception:
            body = request.POST

        question.question_text = body.get('question_text', question.question_text).strip()
        model_answer = body.get('model_answer', question.model_answer)
        if model_answer is not None:
            question.model_answer = model_answer.strip()
        diff = body.get('difficulty', question.difficulty).upper()
        if diff in ('EASY', 'MEDIUM', 'HARD'):
            question.difficulty = diff
        question.is_edited = True
        question.save()

        if request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'ok', 'question_text': question.question_text})

        messages.success(request, "Question updated.")
        return redirect('interview_questions_detail', pk=question.question_set_id)


class DeleteQuestionView(RecruiterRequiredMixin, View):
    """Delete a single InterviewQuestion."""

    def post(self, request, pk):
        question = get_object_or_404(InterviewQuestion, pk=pk)
        qs_pk = question.question_set_id
        question.delete()
        messages.success(request, "Question removed.")
        return redirect('interview_questions_detail', pk=qs_pk)


# ─────────────────────────────────────────────────────────────────────────────
# Module 7 — Interview Intelligence
# ─────────────────────────────────────────────────────────────────────────────

class UploadTranscriptView(RecruiterRequiredMixin, View):
    """
    GET  → Show dual-tab form: audio upload OR text paste.
    POST → If audio file provided: Groq Whisper STT → transcript.
            Then: interview intelligence analysis → InterviewSummary.
    """

    def get(self, request, application_pk):
        application = get_object_or_404(Application, pk=application_pk)
        return render(request, 'interviews/upload_transcript.html', {'application': application})

    def post(self, request, application_pk):
        application = get_object_or_404(Application, pk=application_pk)
        source      = 'MANUAL'
        transcript  = ''

        audio_file = request.FILES.get('audio_file')
        if audio_file:
            # ── Path 1: Audio → Groq Whisper STT ──────────────────────────────
            from django.core.files.storage import default_storage
            from django.core.files.base import ContentFile

            audio_path = default_storage.save(
                f'interview_audio/tmp_{application_pk}_{audio_file.name}',
                ContentFile(audio_file.read())
            )
            full_path = os.path.join(
                os.environ.get('MEDIA_ROOT', 'media'),
                audio_path
            )
            transcript = transcribe_audio_with_groq(full_path)
            if not transcript:
                messages.error(request, "Audio transcription failed. Please paste the transcript manually.")
                return redirect('upload_transcript', application_pk=application_pk)
            source = 'AUDIO_STT'
            # Store audio reference on the summary (done below via engine)
        else:
            # ── Path 2: Manual text paste ──────────────────────────────────────
            transcript = request.POST.get('transcript', '').strip()
            if not transcript:
                messages.error(request, "Please upload an audio file or paste the transcript text.")
                return redirect('upload_transcript', application_pk=application_pk)

        # ── Run intelligence analysis ──────────────────────────────────────────
        summary_obj = generate_interview_intelligence(application, transcript, source=source)

        if not summary_obj:
            messages.error(request, "Failed to analyze the interview transcript. Please try again.")
            return redirect('upload_transcript', application_pk=application_pk)

        # Attach audio file reference if uploaded
        if audio_file and summary_obj:
            try:
                summary_obj.audio_file = audio_path
                summary_obj.save(update_fields=['audio_file'])
            except Exception:
                pass

        messages.success(request, "Interview Intelligence analysis complete!")
        return redirect('summary_detail', pk=summary_obj.pk)


class InterviewSummaryDetailView(RecruiterRequiredMixin, DetailView):
    """Recruiter view: full intelligence panel with transcript, scores, strengths, weaknesses, recommendation."""
    model = InterviewSummary
    template_name = 'interviews/summary_detail.html'
    context_object_name = 'summary'


class ExportSummaryPDFView(RecruiterRequiredMixin, View):
    def get(self, request, pk):
        from django.template.loader import get_template
        from xhtml2pdf import pisa
        summary_obj = get_object_or_404(InterviewSummary, pk=pk)
        template = get_template('interviews/summary_pdf.html')
        html = template.render({'summary': summary_obj})
        response = HttpResponse(content_type='application/pdf')
        fname = summary_obj.application.candidate.user.get_full_name().replace(' ', '_')
        response['Content-Disposition'] = f'attachment; filename="interview_intelligence_{fname}.pdf"'
        pisa_status = pisa.CreatePDF(html, dest=response)
        if pisa_status.err:
            return HttpResponse('PDF generation error: <pre>' + html + '</pre>')
        return response


# ─────────────────────────────────────────────────────────────────────────────
# Interview Scheduling
# ─────────────────────────────────────────────────────────────────────────────

class InterviewScheduleCreateView(RecruiterRequiredMixin, View):
    def get(self, request, application_pk):
        application = get_object_or_404(Application, pk=application_pk)
        return render(request, 'interviews/schedule_form.html', {'application': application})

    def post(self, request, application_pk):
        application = get_object_or_404(Application, pk=application_pk)

        scheduled_time_str = request.POST.get('scheduled_time')
        duration       = request.POST.get('duration_minutes', 60)
        meeting_link   = request.POST.get('meeting_link', '').strip()
        notes          = request.POST.get('notes', '').strip()
        interview_type = request.POST.get('interview_type', 'TECHNICAL')

        if not scheduled_time_str:
            messages.error(request, "Scheduled time is required.")
            return redirect('schedule_interview', application_pk=application.pk)

        scheduled_time = parse_datetime(scheduled_time_str)
        if not scheduled_time:
            messages.error(request, "Invalid date/time format.")
            return redirect('schedule_interview', application_pk=application.pk)

        schedule = InterviewSchedule.objects.create(
            application      = application,
            scheduled_time   = scheduled_time,
            duration_minutes = int(duration),
            interview_type   = interview_type,
            meeting_link     = meeting_link,
            notes            = notes,
        )

        old_status = application.status
        application.status = 'INTERVIEW'
        application.save()

        from applications.models import WorkflowLog
        WorkflowLog.objects.create(
            application     = application,
            previous_status = old_status,
            new_status      = 'INTERVIEW',
            notes           = f"Interview scheduled ({schedule.get_interview_type_display()}) for {scheduled_time.strftime('%Y-%m-%d %H:%M')}",
        )

        Notification.objects.create(
            user    = application.candidate.user,
            message = (
                f"An interview ({schedule.get_interview_type_display()}) has been scheduled for "
                f"your application to {application.job.title} on {scheduled_time.strftime('%B %d, %Y at %I:%M %p')}."
            ),
        )

        messages.success(request, "Interview scheduled successfully and candidate notified.")
        return redirect('scheduled_interviews')


class ScheduledInterviewsListView(RecruiterRequiredMixin, ListView):
    model = InterviewSchedule
    template_name = 'interviews/scheduled_list.html'
    context_object_name = 'interviews'
    paginate_by = 20

    def get_queryset(self):
        qs = InterviewSchedule.objects.select_related(
            'application__candidate__user', 'application__job'
        ).order_by('scheduled_time')

        user = self.request.user
        if user.role != 'ADMIN':
            company = None
            if user.role == 'COMPANY' and hasattr(user, 'owned_company'):
                company = user.owned_company
            elif user.role == 'RECRUITER' and hasattr(user, 'company'):
                company = user.company
            if company:
                qs = qs.filter(application__job__company=company)
            else:
                return InterviewSchedule.objects.none()

        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_status'] = self.request.GET.get('status', '')
        return context


class InterviewStatusUpdateView(RecruiterRequiredMixin, View):
    def post(self, request, pk):
        interview    = get_object_or_404(InterviewSchedule, pk=pk)
        new_status   = request.POST.get('status')
        new_time_str = request.POST.get('scheduled_time')
        notes        = request.POST.get('notes', '').strip()

        if new_status in ('SCHEDULED', 'COMPLETED', 'CANCELLED', 'RESCHEDULED'):
            interview.status = new_status
            if new_time_str:
                parsed_time = parse_datetime(new_time_str)
                if parsed_time:
                    interview.scheduled_time = parsed_time
            if notes:
                interview.notes = notes
            interview.save()

            Notification.objects.create(
                user    = interview.application.candidate.user,
                message = f"Your interview for {interview.application.job.title} status has been updated to: {interview.get_status_display()}.",
            )
            messages.success(request, f"Interview status updated to {interview.get_status_display()}.")
        return redirect('scheduled_interviews')


class CandidateInterviewsListView(LoginRequiredMixin, ListView):
    """Candidate view — only shows schedule, type, status. No recruiter evaluation."""
    model = InterviewSchedule
    template_name = 'interviews/candidate_list.html'
    context_object_name = 'interviews'

    def get_queryset(self):
        try:
            profile = self.request.user.candidate_profile
            return InterviewSchedule.objects.filter(
                application__candidate=profile
            ).select_related('application__job', 'application__job__company').order_by('scheduled_time')
        except Exception:
            return InterviewSchedule.objects.none()
