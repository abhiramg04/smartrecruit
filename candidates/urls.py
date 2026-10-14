from django.urls import path
from .views import (
    ResumeUploadView, CandidateProfileView, CandidateProfileEditView, RecruiterCandidateListView,
    RecruiterCandidateDetailView, ResumeDeleteView, SecureResumeDownloadView
)

urlpatterns = [
    path('upload/', ResumeUploadView.as_view(), name='resume_upload'),
    path('profile/', CandidateProfileView.as_view(), name='candidate_profile'),
    path('profile/edit/', CandidateProfileEditView.as_view(), name='candidate_profile_edit'),
    path('resume/delete/', ResumeDeleteView.as_view(), name='resume_delete'),
    path('<int:pk>/resume/download/', SecureResumeDownloadView.as_view(), name='secure_resume_download'),
    # Recruiter-facing views
    path('all/', RecruiterCandidateListView.as_view(), name='recruiter_candidate_list'),
    path('<int:pk>/view/', RecruiterCandidateDetailView.as_view(), name='recruiter_candidate_detail'),
]
