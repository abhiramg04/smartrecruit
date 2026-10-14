from django.urls import path
from .views import (
    JobListView, JobDetailView, JobCreateView, JobUpdateView,
    JobDeleteView, JobStatusToggleView, CompanyJobListView,
    JobApproveView, JobRejectView,
)

urlpatterns = [
    path('', JobListView.as_view(), name='job_list'),
    path('manage/', CompanyJobListView.as_view(), name='company_job_list'),
    path('<int:pk>/', JobDetailView.as_view(), name='job_detail'),
    path('<int:pk>/approve/', JobApproveView.as_view(), name='job_approve'),
    path('<int:pk>/reject/', JobRejectView.as_view(), name='job_reject'),
    path('create/', JobCreateView.as_view(), name='job_create'),
    path('<int:pk>/update/', JobUpdateView.as_view(), name='job_update'),
    path('<int:pk>/delete/', JobDeleteView.as_view(), name='job_delete'),
    path('<int:pk>/status/<str:action>/', JobStatusToggleView.as_view(), name='job_status_toggle'),
]
