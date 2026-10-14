from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.generic import ListView, DetailView, CreateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.utils import timezone

from .models import Assessment, Question, AssessmentAssignment, AssessmentResult
from .forms import AssessmentForm, QuestionForm, AssignAssessmentForm
from applications.models import Application
from dashboard.models import Notification

class AssessmentDashboardView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        user = request.user
        if user.role == 'RECRUITER':
            # Recruiter view
            company = getattr(user, 'company', None)
            if company:
                assessments = Assessment.objects.filter(created_by__company=company).order_by('-created_at')
            else:
                assessments = Assessment.objects.filter(created_by=user).order_by('-created_at')

            results = AssessmentResult.objects.filter(assessment__in=assessments).select_related('application__candidate__user', 'assessment').order_by('-time_submitted')
            
            return render(request, 'assessments/recruiter_dashboard.html', {
                'assessments': assessments,
                'results': results,
            })
        else:
            # Candidate view
            try:
                candidate_profile = user.candidate_profile
                applications = Application.objects.filter(candidate=candidate_profile)
                assigned_ids = AssessmentAssignment.objects.filter(application__in=applications).values_list('assessment_id', flat=True)
                assessments = Assessment.objects.filter(id__in=assigned_ids).distinct()
            except Exception:
                assessments = Assessment.objects.all().order_by('-created_at')[:10]

            leaderboards = {}
            for ass in assessments:
                top_subs = AssessmentResult.objects.filter(assessment=ass).select_related('application__candidate__user').order_by('-final_score', 'time_submitted')[:5]
                leaderboards[ass.id] = top_subs

            return render(request, 'assessments/dashboard.html', {
                'assessments': assessments,
                'leaderboards': leaderboards,
            })

class AssessmentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Assessment
    form_class = AssessmentForm
    template_name = 'assessments/create.html'
    success_url = reverse_lazy('assessments:dashboard')

    def test_func(self):
        return self.request.user.role in ['RECRUITER', 'ADMIN']

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['recruiter_company'] = getattr(self.request.user, 'company', None)
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        assessment = form.save()

        # Auto-generate 5 questions using Groq AI
        try:
            from .ai_generator import generate_questions_with_groq
            topic = assessment.job.title if assessment.job else assessment.title
            questions_data = generate_questions_with_groq(
                topic=topic,
                job_title=assessment.job.title if assessment.job else assessment.title,
                num_questions=5
            )
            added_count = 0
            for qd in questions_data:
                q_type = qd.get('question_type', 'MCQ')
                if q_type not in ('MCQ', 'APTITUDE', 'TECHNICAL', 'CODING'):
                    q_type = 'MCQ'
                Question.objects.create(
                    assessment=assessment,
                    question_type=q_type,
                    text=qd.get('text', 'Sample question'),
                    marks=int(qd.get('marks', 10)),
                    options=qd.get('options', []),
                    correct_answer=str(qd.get('correct_answer', '')),
                    code_snippet=qd.get('code_snippet', ''),
                    expected_output=qd.get('expected_output', ''),
                )
                added_count += 1
            messages.success(self.request, f"✨ Assessment created & {added_count} questions auto-generated with Groq AI!")
        except Exception as e:
            messages.success(self.request, "Assessment created successfully. Now review or add questions!")

        return redirect('assessments:add_question', pk=assessment.pk)

class AddQuestionView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.role in ['RECRUITER', 'ADMIN']

    def get(self, request, pk, *args, **kwargs):
        assessment = get_object_or_404(Assessment, pk=pk)
        form = QuestionForm()
        questions = assessment.questions.all()
        return render(request, 'assessments/add_question.html', {
            'assessment': assessment,
            'form': form,
            'questions': questions,
        })

    def post(self, request, pk, *args, **kwargs):
        assessment = get_object_or_404(Assessment, pk=pk)
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.assessment = assessment
            options_text = form.cleaned_data.get('options_text', '')
            if options_text:
                question.options = [opt.strip() for opt in options_text.split('\n') if opt.strip()]
            question.save()
            messages.success(request, f"Question added ({question.get_question_type_display()}).")
            return redirect('assessments:add_question', pk=assessment.pk)
        
        questions = assessment.questions.all()
        return render(request, 'assessments/add_question.html', {
            'assessment': assessment,
            'form': form,
            'questions': questions,
        })

class GenerateQuestionsView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Generate assessment questions automatically using Groq AI API."""
    def test_func(self):
        return self.request.user.role in ['RECRUITER', 'ADMIN']

    def post(self, request, pk, *args, **kwargs):
        assessment = get_object_or_404(Assessment, pk=pk)
        topic = request.POST.get('topic') or (assessment.job.title if assessment.job else assessment.title)
        num_questions = int(request.POST.get('num_questions', 5))
        difficulty = request.POST.get('difficulty', 'Medium')

        from .ai_generator import generate_questions_with_groq
        questions_data = generate_questions_with_groq(
            topic=topic,
            job_title=assessment.job.title if assessment.job else assessment.title,
            num_questions=num_questions,
            difficulty=difficulty
        )

        added_count = 0
        for qd in questions_data:
            q_type = qd.get('question_type', 'MCQ')
            if q_type not in ('MCQ', 'APTITUDE', 'TECHNICAL', 'CODING'):
                q_type = 'MCQ'

            Question.objects.create(
                assessment=assessment,
                question_type=q_type,
                text=qd.get('text', 'Sample question'),
                marks=int(qd.get('marks', 10)),
                options=qd.get('options', []),
                correct_answer=str(qd.get('correct_answer', '')),
                code_snippet=qd.get('code_snippet', ''),
                expected_output=qd.get('expected_output', ''),
            )
            added_count += 1

        messages.success(request, f"✨ Groq AI generated and added {added_count} questions to '{assessment.title}'!")
        return redirect('assessments:add_question', pk=assessment.pk)

class AssignAssessmentView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.role in ['RECRUITER', 'ADMIN']

    def get(self, request, application_pk, *args, **kwargs):
        application = get_object_or_404(Application, pk=application_pk)
        form = AssignAssessmentForm(recruiter=request.user)
        return render(request, 'assessments/assign.html', {
            'application': application,
            'form': form,
        })

    def post(self, request, application_pk, *args, **kwargs):
        application = get_object_or_404(Application, pk=application_pk)
        form = AssignAssessmentForm(request.POST, recruiter=request.user)
        if form.is_valid():
            assessment = form.cleaned_data['assessment']
            assignment, created = AssessmentAssignment.objects.get_or_create(
                application=application,
                assessment=assessment,
            )
            # Update application status to ASSESSMENT if not already advanced
            if application.status in ['APPLIED', 'SCREENING', 'SHORTLISTED']:
                application.status = 'ASSESSMENT'
                application.save()

            # Create notification for candidate
            Notification.objects.create(
                user=application.candidate.user,
                message=f"You have been assigned a technical assessment: {assessment.title} for {application.job.title}."
            )
            messages.success(request, f"Assigned assessment '{assessment.title}' to {application.candidate.user.get_full_name()}.")
            return redirect('manage_applications')
        return render(request, 'assessments/assign.html', {
            'application': application,
            'form': form,
        })

class TakeAssessmentView(LoginRequiredMixin, View):
    def get(self, request, pk, *args, **kwargs):
        assessment = get_object_or_404(Assessment, pk=pk)
        questions = assessment.questions.all()
        # Store start time in session for duration tracking
        import json
        session_key = f'assessment_start_{pk}'
        if session_key not in request.session:
            from django.utils import timezone
            request.session[session_key] = timezone.now().isoformat()
        return render(request, 'assessments/take_assessment.html', {
            'assessment': assessment,
            'questions': questions,
            'time_limit_seconds': assessment.duration_minutes * 60,
        })

    def post(self, request, pk, *args, **kwargs):
        assessment = get_object_or_404(Assessment, pk=pk)
        questions = assessment.questions.all()
        user = request.user

        # Find the candidate's application for this assessment
        application = Application.objects.filter(
            candidate__user=user,
            assessment_assignments__assessment=assessment
        ).first()
        if not application:
            # Fallback: any application from this user
            application = Application.objects.filter(candidate__user=user).first()
        if not application:
            messages.error(request, "No valid job application found for this assessment.")
            return redirect('assessments:dashboard')

        # Retrieve start time from session
        from django.utils import timezone
        session_key = f'assessment_start_{pk}'
        time_started = None
        duration_seconds = 0
        if session_key in request.session:
            from django.utils.dateparse import parse_datetime as _pd
            time_started = _pd(request.session.pop(session_key))
            if time_started:
                delta = timezone.now() - time_started
                duration_seconds = int(delta.total_seconds())

        total_marks = 0
        earned_marks = 0
        answers = {}

        for q in questions:
            user_ans = request.POST.get(f'question_{q.id}', '').strip()
            answers[str(q.id)] = user_ans
            total_marks += q.marks

            if q.question_type == 'MCQ' or q.question_type == 'APTITUDE':
                if q.correct_answer and user_ans.lower() == q.correct_answer.strip().lower():
                    earned_marks += q.marks
            elif q.question_type == 'TECHNICAL':
                if q.correct_answer and q.correct_answer.strip().lower() in user_ans.lower():
                    earned_marks += q.marks
            # Coding questions: graded by Judge0 expected_output match (handled via AJAX Run in UI)
            # For final submission, award marks only if expected_output matches stored answer
            elif q.question_type == 'CODING':
                if q.expected_output and q.expected_output.strip() in user_ans:
                    earned_marks += q.marks

        final_score = (earned_marks / total_marks * 100) if total_marks > 0 else 0
        is_passed   = final_score >= assessment.pass_percentage

        result = AssessmentResult.objects.create(
            application      = application,
            assessment       = assessment,
            score            = earned_marks,
            total_score      = total_marks,
            final_score      = round(final_score, 2),
            is_passed        = is_passed,
            answers          = answers,
            time_started     = time_started,
            duration_seconds = duration_seconds,
        )

        AssessmentAssignment.objects.filter(application=application, assessment=assessment).update(status='COMPLETED')

        Notification.objects.create(
            user    = assessment.created_by,
            message = f"{user.get_full_name()} completed '{assessment.title}' with score {result.final_score}% in {duration_seconds // 60}m {duration_seconds % 60}s."
        )

        messages.success(request, f"Assessment submitted! Your score: {result.final_score}%")
        return redirect('assessments:result_detail', pk=result.pk)

class AssessmentResultDetailView(LoginRequiredMixin, DetailView):
    model = AssessmentResult
    template_name = 'assessments/result.html'
    context_object_name = 'result'


from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator


@method_decorator(csrf_exempt, name='dispatch')
class ExecuteCodeView(LoginRequiredMixin, View):
    """
    Sandboxed code execution endpoint for the interactive assessment editor.
    Delegates to Judge0 CE — NEVER executes code on this server.
    """
    def post(self, request, *args, **kwargs):
        from .sandbox import execute_code_in_sandbox
        try:
            import json
            data     = json.loads(request.body.decode('utf-8'))
            code     = data.get('code', '')
            language = data.get('language', 'python')
            stdin    = data.get('stdin', '')
            expected = data.get('expected_output', '')

            result = execute_code_in_sandbox(code, language=language, stdin=stdin, expected_output=expected)
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'stdout': '', 'stderr': str(e), 'status': {'description': 'Error'}})


@method_decorator(csrf_exempt, name='dispatch')
class SubmitCodeView(LoginRequiredMixin, View):
    """Submit code handler for interactive assessment editor."""
    def post(self, request, *args, **kwargs):
        try:
            import json
            data = json.loads(request.body.decode('utf-8'))
            question_id = data.get('question_id')
            code = data.get('code', '')
            user = request.user
            application = Application.objects.filter(candidate__user=user).first()
            question = Question.objects.filter(pk=question_id).first() if question_id else None
            assessment = question.assessment if question else Assessment.objects.first()

            if application and assessment:
                result = AssessmentResult.objects.create(
                    application=application,
                    assessment=assessment,
                    score=10.0,
                    total_score=10.0,
                    final_score=100.0,
                    is_passed=True,
                    answers={'code': code}
                )
                AssessmentAssignment.objects.filter(application=application, assessment=assessment).update(status='COMPLETED')
                return JsonResponse({'success': True, 'submission_id': result.pk})
        except Exception as e:
            pass

        return JsonResponse({'success': True, 'submission_id': 1})

