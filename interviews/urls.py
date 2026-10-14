from django.urls import path
from .views import (
    # Module 5 — Question Generator
    GenerateQuestionsView,
    QuestionSetDetailView,
    EditQuestionView,
    DeleteQuestionView,
    # Module 7 — Interview Intelligence
    UploadTranscriptView,
    InterviewSummaryDetailView,
    ExportSummaryPDFView,
    # Scheduling
    InterviewScheduleCreateView,
    ScheduledInterviewsListView,
    InterviewStatusUpdateView,
    CandidateInterviewsListView,
)

urlpatterns = [
    # Module 5 — Question Generator
    path('generate/<int:application_pk>/',        GenerateQuestionsView.as_view(),  name='generate_interview_questions'),
    path('detail/<int:pk>/',                       QuestionSetDetailView.as_view(),  name='interview_questions_detail'),
    path('question/<int:pk>/edit/',               EditQuestionView.as_view(),        name='edit_interview_question'),
    path('question/<int:pk>/delete/',             DeleteQuestionView.as_view(),      name='delete_interview_question'),

    # Module 7 — Interview Intelligence
    path('summary/upload/<int:application_pk>/',  UploadTranscriptView.as_view(),          name='upload_transcript'),
    path('summary/detail/<int:pk>/',              InterviewSummaryDetailView.as_view(),     name='summary_detail'),
    path('summary/export/<int:pk>/',              ExportSummaryPDFView.as_view(),           name='export_summary_pdf'),

    # Scheduling
    path('schedule/<int:application_pk>/',        InterviewScheduleCreateView.as_view(),    name='schedule_interview'),
    path('scheduled/',                            ScheduledInterviewsListView.as_view(),    name='scheduled_interviews'),
    path('my/',                                   CandidateInterviewsListView.as_view(),    name='my_interviews'),
    path('scheduled/<int:pk>/status/',            InterviewStatusUpdateView.as_view(),      name='interview_status_update'),
]
