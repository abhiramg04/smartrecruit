from django.urls import path
from .views import (
    SkillGapSelectView, SkillGapAnalyzeView, SkillGapReportView, SkillGapPrintView,
    AssessmentListView, CandidateMyAssessmentsView, AssessmentCreateView, AssessmentTakeView
)

urlpatterns = [
    path('', SkillGapSelectView.as_view(), name='skill_gap_select'),
    path('analyze/', SkillGapAnalyzeView.as_view(), name='skill_gap_analyze'),
    path('report/<int:pk>/', SkillGapReportView.as_view(), name='skill_gap_report'),
    path('report/<int:pk>/print/', SkillGapPrintView.as_view(), name='skill_gap_print'),
    
    # Technical Skill Assessment Routes
    path('assessments/', AssessmentListView.as_view(), name='assessment_list'),
    path('my-assessments/', CandidateMyAssessmentsView.as_view(), name='my_assessments'),
    path('assessments/create/', AssessmentCreateView.as_view(), name='assessment_create'),
    path('assessments/<int:pk>/take/', AssessmentTakeView.as_view(), name='assessment_take'),
]
