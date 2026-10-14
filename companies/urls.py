from django.urls import path
from .views import (
    CompanyCreateView, CompanyUpdateView, CompanyDetailView,
    CompanyProfileView, CompanyApproveView, CompanyRejectView,
)

urlpatterns = [
    path('create/', CompanyCreateView.as_view(), name='company_create'),
    path('profile/', CompanyProfileView.as_view(), name='company_profile'),
    path('<int:pk>/update/', CompanyUpdateView.as_view(), name='company_update'),
    path('<int:pk>/approve/', CompanyApproveView.as_view(), name='company_approve'),
    path('<int:pk>/reject/', CompanyRejectView.as_view(), name='company_reject'),
    path('<int:pk>/', CompanyDetailView.as_view(), name='company_detail'),
]
