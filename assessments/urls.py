from django.urls import path
from .views import (
    AssessmentDashboardView, AssessmentCreateView, AddQuestionView,
    AssignAssessmentView, TakeAssessmentView, AssessmentResultDetailView,
    ExecuteCodeView, SubmitCodeView, GenerateQuestionsView
)

app_name = 'assessments'

urlpatterns = [
    path('', AssessmentDashboardView.as_view(), name='dashboard'),
    path('list/', AssessmentDashboardView.as_view(), name='assessment_list'),
    path('my/', AssessmentDashboardView.as_view(), name='my_assessments'),
    path('create/', AssessmentCreateView.as_view(), name='create'),
    path('<int:pk>/questions/', AddQuestionView.as_view(), name='add_question'),
    path('<int:pk>/generate-questions/', GenerateQuestionsView.as_view(), name='generate_questions'),
    path('assign/<int:application_pk>/', AssignAssessmentView.as_view(), name='assign'),
    path('take/<int:pk>/', TakeAssessmentView.as_view(), name='take_assessment'),
    path('result/<int:pk>/', AssessmentResultDetailView.as_view(), name='result_detail'),
    path('execute-code/', ExecuteCodeView.as_view(), name='execute_code'),
    path('submit-code/', SubmitCodeView.as_view(), name='submit_code'),
]
