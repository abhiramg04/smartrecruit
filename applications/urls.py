from django.urls import path
from .views import (
    ApplyView, MyApplicationsView, ApplicationDetailView,
    WorkflowUpdateView, ManageApplicationsView, ApplicationQuickActionView, HiringDecisionView
)

urlpatterns = [
    path('apply/<int:job_pk>/', ApplyView.as_view(), name='apply_job'),
    path('my/', MyApplicationsView.as_view(), name='my_applications'),
    path('manage/', ManageApplicationsView.as_view(), name='manage_applications'),
    path('<int:pk>/', ApplicationDetailView.as_view(), name='application_detail'),
    path('<int:pk>/workflow/', ApplicationDetailView.as_view(), name='application_workflow'),
    path('<int:pk>/status/update/', WorkflowUpdateView.as_view(), name='workflow_update'),
    path('<int:pk>/action/<str:action>/', ApplicationQuickActionView.as_view(), name='application_quick_action'),
    path('<int:pk>/hiring-decision/', HiringDecisionView.as_view(), name='hiring_decision'),
]
