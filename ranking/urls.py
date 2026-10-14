from django.urls import path
from .views import TriggerRankingView, RankingResultView, RankingDashboardView, RecruiterCandidateListView

urlpatterns = [
    path('', RecruiterCandidateListView.as_view(), name='recruiter_candidate_list'),
    path('rank/<int:application_pk>/', TriggerRankingView.as_view(), name='trigger_ranking'),
    path('result/<int:pk>/', RankingResultView.as_view(), name='ranking_result'),
    path('dashboard/<int:job_pk>/', RankingDashboardView.as_view(), name='ranking_dashboard'),
]
