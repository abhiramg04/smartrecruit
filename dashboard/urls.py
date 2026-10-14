from django.urls import path
from .views import (
    AdminDashboardView, AdminApprovalListView, AdminUserManagementView, AdminUserActionView,
    AdminRecruiterListView, AdminCandidateListView,
    CompanyDashboardView, RecruiterDashboardView, CandidateDashboardView,
    NotificationListView, MarkNotificationReadView, NotificationUnreadCountView, ReportsDashboardView,
    AdminCategoryListView, AdminCategoryCreateView, AdminCategoryUpdateView, AdminCategoryDeleteView, AdminCategoryToggleView,
    AdminSystemConfigView, AdminAIConfigView, AdminAuditLogListView, AdminBackupSecurityView, ExportDatabaseView
)
from .analytics_views import AnalyticsDashboardView, AnalyticsDataAPIView

urlpatterns = [
    path('admin/', AdminDashboardView.as_view(), name='admin_dashboard'),
    path('admin/approvals/', AdminApprovalListView.as_view(), name='admin_approvals'),
    path('admin/users/', AdminUserManagementView.as_view(), name='admin_users'),
    path('admin/recruiters/', AdminRecruiterListView.as_view(), name='admin_recruiters'),
    path('admin/candidates/', AdminCandidateListView.as_view(), name='admin_candidates'),
    path('admin/users/<int:pk>/action/', AdminUserActionView.as_view(), name='admin_user_action'),
    path('company/', CompanyDashboardView.as_view(), name='company_dashboard'),
    path('recruiter/', RecruiterDashboardView.as_view(), name='recruiter_dashboard'),
    path('candidate/', CandidateDashboardView.as_view(), name='candidate_dashboard'),
    path('reports/', ReportsDashboardView.as_view(), name='reports_dashboard'),
    path('admin/audit-logs/', AdminAuditLogListView.as_view(), name='admin_audit_logs'),
    path('admin/backup-security/', AdminBackupSecurityView.as_view(), name='admin_backup_security'),
    path('admin/backup-security/export/', ExportDatabaseView.as_view(), name='export_database'),
    
    # Analytics Endpoints
    path('analytics/', AnalyticsDashboardView.as_view(), name='analytics_dashboard'),
    path('api/analytics/', AnalyticsDataAPIView.as_view(), name='analytics_api'),

    # Notification Endpoints
    path('notifications/', NotificationListView.as_view(), name='notification_list'),
    path('notifications/read/all/', MarkNotificationReadView.as_view(), name='mark_all_notifications_read'),
    path('notifications/read/<int:pk>/', MarkNotificationReadView.as_view(), name='mark_notification_read'),
    path('notifications/unread-count/', NotificationUnreadCountView.as_view(), name='notification_unread_count'),
    
    # Job Category Management
    path('admin/categories/', AdminCategoryListView.as_view(), name='admin_categories'),
    path('admin/categories/add/', AdminCategoryCreateView.as_view(), name='admin_category_add'),
    path('admin/categories/<int:pk>/edit/', AdminCategoryUpdateView.as_view(), name='admin_category_edit'),
    path('admin/categories/<int:pk>/delete/', AdminCategoryDeleteView.as_view(), name='admin_category_delete'),
    path('admin/categories/<int:pk>/toggle/', AdminCategoryToggleView.as_view(), name='admin_category_toggle'),

    # System Configuration
    path('admin/system-config/', AdminSystemConfigView.as_view(), name='admin_system_config'),
    
    # AI Configuration
    path('admin/ai-config/', AdminAIConfigView.as_view(), name='admin_ai_config'),
]
