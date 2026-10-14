from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from companies.models import Company
from .models import Notification
from .analytics import AnalyticsService

class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'dashboard/admin.html'
    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def get_context_data(self, **kwargs):
        from jobs.models import Job
        from accounts.models import CustomUser
        context = super().get_context_data(**kwargs)
        context['total_companies']   = Company.objects.filter(is_approved=True).count()
        context['total_candidates']  = CustomUser.objects.filter(role='CANDIDATE').count()
        context['pending_companies'] = Company.objects.filter(is_approved=False).count()
        context['pending_jobs']      = Job.objects.filter(is_approved=False).count()
        context['pending_total']     = context['pending_companies'] + context['pending_jobs']
        context['admin_analytics']   = AnalyticsService.get_admin_analytics()
        return context
        
class AdminApprovalListView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'dashboard/admin_approvals.html'
    
    def test_func(self):
        return self.request.user.role == 'ADMIN'
        
    def get_context_data(self, **kwargs):
        from jobs.models import Job
        context = super().get_context_data(**kwargs)
        context['pending_companies'] = Company.objects.filter(is_approved=False)
        context['pending_jobs'] = Job.objects.filter(is_approved=False)
        return context

class CompanyDashboardView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return redirect('recruiter_dashboard')

class RecruiterDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'dashboard/recruiter.html'

    def test_func(self):
        return self.request.user.role in ['RECRUITER', 'COMPANY', 'ADMIN']

    def get_context_data(self, **kwargs):
        from jobs.models import Job
        from applications.models import Application
        from interviews.models import InterviewSchedule
        from assessments.models import Assessment, AssessmentAssignment, AssessmentResult

        context = super().get_context_data(**kwargs)
        company = getattr(self.request.user, 'company', None) or getattr(self.request.user, 'owned_company', None)
        context['company'] = company
        
        if company:
            jobs = Job.objects.filter(company=company)
            applications = Application.objects.filter(job__company=company)
            interviews = InterviewSchedule.objects.filter(application__job__company=company)
            assessments = Assessment.objects.filter(created_by__company=company)

            context['jobs'] = jobs.order_by('-created_at')[:5]
            context['total_jobs_count'] = jobs.count()
            context['active_jobs_count'] = jobs.filter(is_published=True, is_closed=False).count()
            context['draft_jobs_count'] = jobs.filter(is_published=False, is_closed=False).count()
            context['closed_jobs_count'] = jobs.filter(is_closed=True).count()

            context['total_applications'] = applications.count()
            context['pending_applications'] = applications.filter(status='APPLIED').count()
            context['shortlisted_count'] = applications.filter(status='SHORTLISTED').count()
            context['hold_count'] = applications.filter(status='HOLD').count()
            context['selected_count'] = applications.filter(status='OFFER').count()
            context['rejected_count'] = applications.filter(status='REJECTED').count()

            context['interviews_count'] = interviews.filter(status='SCHEDULED').count()
            context['assessments_count'] = assessments.count()
            context['assessment_results_count'] = AssessmentResult.objects.filter(assessment__in=assessments).count()

            context['recent_applications'] = applications.select_related('candidate__user', 'job').order_by('-applied_at')[:8]
            context['upcoming_interviews'] = interviews.select_related('application__candidate__user', 'application__job').filter(status='SCHEDULED').order_by('scheduled_time')[:5]

            # Attach aggregated analytics & hiring funnel
            recruiter_analytics = AnalyticsService.get_recruiter_analytics(self.request.user)
            context['analytics'] = recruiter_analytics
            context['funnel'] = recruiter_analytics.get('funnel', [])
            context['ai_analytics'] = AnalyticsService.get_ai_analytics(self.request.user)
        else:
            context['jobs'] = []
            context['total_jobs_count'] = 0
            context['active_jobs_count'] = 0
            context['draft_jobs_count'] = 0
            context['closed_jobs_count'] = 0
            context['total_applications'] = 0
            context['pending_applications'] = 0
            context['shortlisted_count'] = 0
            context['hold_count'] = 0
            context['selected_count'] = 0
            context['rejected_count'] = 0
            context['interviews_count'] = 0
            context['assessments_count'] = 0
            context['assessment_results_count'] = 0
            context['recent_applications'] = []
            context['upcoming_interviews'] = []
            context['analytics'] = AnalyticsService._empty_recruiter_stats()
            context['funnel'] = []
            context['ai_analytics'] = {}

        context['notifications'] = Notification.objects.filter(user=self.request.user, is_read=False)[:5]
        return context


class CandidateDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'dashboard/candidate.html'
    def test_func(self):
        return self.request.user.role == 'CANDIDATE'

    def get_context_data(self, **kwargs):
        from candidates.models import CandidateProfile
        
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        completeness = 20
        messages = []
        
        if user.profile_photo:
            completeness += 20
        else:
            messages.append("Upload a profile picture to reach {}%")
            
        if user.bio:
            completeness += 20
        else:
            messages.append("Add a bio to reach {}%")
            
        has_resume = False
        try:
            profile = user.candidate_profile
            if profile.resume_file:
                has_resume = True
                completeness += 40
            else:
                messages.append("Upload your resume to reach {}%")
        except CandidateProfile.DoesNotExist:
            messages.append("Upload your resume to reach {}%")
            profile = None
            
        context['profile_completeness'] = completeness
        
        if completeness >= 100:
            context['completeness_message'] = "Profile is complete!"
        else:
            if messages:
                next_pct = completeness + (40 if 'resume' in messages[0] else 20)
                context['completeness_message'] = messages[0].format(next_pct)
            else:
                context['completeness_message'] = "Complete your profile"
                
        # Calculate application metrics
        from applications.models import Application
        if hasattr(user, 'candidate_profile'):
            apps = Application.objects.filter(candidate=user.candidate_profile)
            context['applications_count'] = apps.count()
            context['interviews_count'] = apps.filter(status='INTERVIEW').count()
            context['shortlisted_count'] = apps.filter(status='SHORTLISTED').count()
            context['offers_count'] = apps.filter(status='OFFER').count()
        else:
            context['applications_count'] = 0
            context['interviews_count'] = 0
            context['shortlisted_count'] = 0
            context['offers_count'] = 0
            
        return context

from django.views import View
from django.shortcuts import redirect

import json as _json
from django.http import JsonResponse

class NotificationListView(LoginRequiredMixin, ListView):
    """Notification history page — shows all notifications with read/unread state."""
    model = Notification
    template_name = 'dashboard/notifications.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user)
        filter_type = self.request.GET.get('type', '')
        if filter_type:
            qs = qs.filter(notification_type=filter_type)
        read_filter = self.request.GET.get('read', '')
        if read_filter == 'unread':
            qs = qs.filter(is_read=False)
        elif read_filter == 'read':
            qs = qs.filter(is_read=True)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['unread_count'] = Notification.unread_count(self.request.user)
        context['notification_types'] = Notification.NOTIFICATION_TYPE_CHOICES
        context['current_type'] = self.request.GET.get('type', '')
        context['current_read'] = self.request.GET.get('read', '')
        return context


class MarkNotificationReadView(LoginRequiredMixin, View):
    """AJAX/form endpoint: mark single or all notifications as read."""
    def post(self, request, pk=None):
        if pk:
            notif = Notification.objects.filter(pk=pk, user=request.user).first()
            if notif:
                notif.is_read = True
                notif.save(update_fields=['is_read'])
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': True, 'unread_count': Notification.unread_count(request.user)})
        else:
            Notification.mark_all_read(request.user)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': True, 'unread_count': 0})

        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect('notification_list')


class NotificationUnreadCountView(LoginRequiredMixin, View):
    """AJAX endpoint: returns unread notification count and latest 5 notifications."""
    def get(self, request):
        count = Notification.unread_count(request.user)
        latest = list(
            Notification.objects.filter(user=request.user, is_read=False)
            .values('id', 'title', 'message', 'notification_type', 'target_url', 'created_at')
            .order_by('-created_at')[:5]
        )
        # Convert datetimes to strings
        for item in latest:
            item['created_at'] = item['created_at'].strftime('%b %d, %H:%M')
        return JsonResponse({'unread_count': count, 'notifications': latest})

import csv
from django.http import HttpResponse
from django.template.loader import render_to_string, get_template
from xhtml2pdf import pisa
from django.utils import timezone
from django.db.models import Avg, Count, Q
from applications.models import Application
from jobs.models import Job
from companies.models import Company

class ReportsDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'dashboard/reports.html'
    
    def test_func(self):
        return self.request.user.role in ['ADMIN', 'COMPANY', 'RECRUITER']

    def get_company(self):
        user = self.request.user
        if user.role == 'COMPANY':
            return getattr(user, 'owned_company', None)
        elif user.role == 'RECRUITER':
            return user.company
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = self.get_company()
        
        # Populate filter dropdowns
        if self.request.user.role == 'ADMIN':
            context['jobs'] = Job.objects.all().order_by('-created_at')
            context['companies'] = Company.objects.all().order_by('name')
        else:
            if company:
                context['jobs'] = Job.objects.filter(company=company).order_by('-created_at')
            else:
                context['jobs'] = Job.objects.none()
            context['companies'] = [company] if company else []
            
        context['application_statuses'] = Application.STATUS_CHOICES
        return context

    def get(self, request, *args, **kwargs):
        if 'generate' in request.GET:
            report_type = request.GET.get('report_type')
            export_format = request.GET.get('format', 'pdf')
            
            if report_type == 'pipeline':
                return self.generate_pipeline_report(request, export_format)
            elif report_type == 'job_performance':
                return self.generate_job_performance_report(request, export_format)
                
        return super().get(request, *args, **kwargs)

    def generate_pipeline_report(self, request, export_format):
        company = self.get_company()
        
        # Build filters
        filters = Q()
        if request.user.role != 'ADMIN':
            if company:
                filters &= Q(job__company=company)
            else:
                filters &= Q(id__isnull=True) # Return empty
                
        job_id = request.GET.get('job_id')
        if job_id:
            filters &= Q(job_id=job_id)
            
        status = request.GET.get('status')
        if status:
            filters &= Q(status=status)
            
        date_from = request.GET.get('date_from')
        if date_from:
            filters &= Q(applied_at__gte=date_from)
            
        date_to = request.GET.get('date_to')
        if date_to:
            filters &= Q(applied_at__lte=date_to)
            
        applications = Application.objects.filter(filters).select_related(
            'candidate__user', 'job'
        ).prefetch_related('ranking_result').order_by('-applied_at')
        
        if export_format == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="pipeline_report_{timezone.now().strftime("%Y%m%d")}.csv"'
            writer = csv.writer(response)
            writer.writerow(['Candidate Email', 'Candidate Name', 'Job Title', 'Applied Date', 'Status', 'Overall AI Score', 'AI Verdict'])
            
            for app in applications:
                score = "N/A"
                verdict = "N/A"
                if hasattr(app, 'ranking_result') and app.ranking_result:
                    score = app.ranking_result.overall_score
                    verdict = app.ranking_result.verdict
                    
                writer.writerow([
                    app.candidate.user.email,
                    app.candidate.full_name or app.candidate.user.get_full_name(),
                    app.job.title,
                    app.applied_at.strftime('%Y-%m-%d'),
                    app.get_status_display(),
                    score,
                    verdict
                ])
            return response
            
        elif export_format == 'pdf':
            template = get_template('dashboard/reports/pipeline_pdf.html')
            context = {
                'applications': applications,
                'generated_at': timezone.now(),
                'generated_by': request.user,
                'filters': {
                    'job': Job.objects.filter(pk=job_id).first() if job_id else 'All',
                    'status': dict(Application.STATUS_CHOICES).get(status) if status else 'All',
                    'date_from': date_from or 'Start',
                    'date_to': date_to or 'End'
                }
            }
            html = template.render(context)
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="pipeline_report_{timezone.now().strftime("%Y%m%d")}.pdf"'
            pisa_status = pisa.CreatePDF(html, dest=response)
            if pisa_status.err:
                return HttpResponse('We had some PDF generation errors.')
            return response

    def generate_job_performance_report(self, request, export_format):
        company = self.get_company()
        
        filters = Q()
        if request.user.role != 'ADMIN':
            if company:
                filters &= Q(company=company)
            else:
                filters &= Q(id__isnull=True)
                
        company_id = request.GET.get('company_id')
        if request.user.role == 'ADMIN' and company_id:
            filters &= Q(company_id=company_id)
            
        status = request.GET.get('job_status')
        if status == 'active':
            filters &= Q(is_published=True, is_closed=False)
        elif status == 'closed':
            filters &= Q(is_closed=True)
            
        jobs = Job.objects.filter(filters).annotate(
            total_apps=Count('applications'),
            shortlisted_apps=Count('applications', filter=Q(applications__status__in=['SHORTLISTED', 'INTERVIEW', 'HR_ROUND', 'OFFER'])),
            avg_ai_score=Avg('applications__ranking_result__overall_score')
        ).order_by('-created_at')
        
        if export_format == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="job_performance_report_{timezone.now().strftime("%Y%m%d")}.csv"'
            writer = csv.writer(response)
            writer.writerow(['Job Title', 'Company', 'Category', 'Created Date', 'Status', 'Total Applications', 'Shortlisted', 'Avg AI Score'])
            
            for job in jobs:
                status_str = "Closed" if job.is_closed else ("Published" if job.is_published else "Draft/Pending")
                avg_score = round(job.avg_ai_score, 1) if job.avg_ai_score is not None else "N/A"
                writer.writerow([
                    job.title,
                    job.company.name,
                    job.category.name if job.category else "N/A",
                    job.created_at.strftime('%Y-%m-%d'),
                    status_str,
                    job.total_apps,
                    job.shortlisted_apps,
                    avg_score
                ])
            return response
            
        elif export_format == 'pdf':
            template = get_template('dashboard/reports/job_performance_pdf.html')
            context = {
                'jobs': jobs,
                'generated_at': timezone.now(),
                'generated_by': request.user,
                'filters': {
                    'company': Company.objects.filter(pk=company_id).first() if company_id else 'All',
                    'status': status.capitalize() if status else 'All',
                }
            }
            html = template.render(context)
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="job_performance_report_{timezone.now().strftime("%Y%m%d")}.pdf"'
            pisa_status = pisa.CreatePDF(html, dest=response)
            if pisa_status.err:
                return HttpResponse('We had some PDF generation errors.')
            return response

class AdminUserManagementView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = 'dashboard/admin_users.html'
    context_object_name = 'users'
    paginate_by = 20

    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def get_queryset(self):
        from accounts.models import CustomUser
        role_filter = self.request.GET.get('role')
        search_query = self.request.GET.get('search')
        
        qs = CustomUser.objects.exclude(role='ADMIN').order_by('-date_joined')
        
        if role_filter and role_filter in ['COMPANY', 'RECRUITER', 'CANDIDATE']:
            qs = qs.filter(role=role_filter)
            
        if search_query:
            qs = qs.filter(email__icontains=search_query) | qs.filter(username__icontains=search_query)
            
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_role'] = self.request.GET.get('role', '')
        context['search_query'] = self.request.GET.get('search', '')
        return context

class AdminRecruiterListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = 'dashboard/admin_recruiters.html'
    context_object_name = 'recruiters'
    paginate_by = 20

    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def get_queryset(self):
        from accounts.models import CustomUser
        qs = CustomUser.objects.filter(role='RECRUITER').select_related('company').order_by('-date_joined')
        search_query = self.request.GET.get('search')
        if search_query:
            qs = qs.filter(Q(email__icontains=search_query) | Q(username__icontains=search_query) | Q(first_name__icontains=search_query) | Q(last_name__icontains=search_query))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        return context

class AdminCandidateListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = 'dashboard/admin_candidates.html'
    context_object_name = 'candidates'
    paginate_by = 20

    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def get_queryset(self):
        from accounts.models import CustomUser
        qs = CustomUser.objects.filter(role='CANDIDATE').order_by('-date_joined')
        search_query = self.request.GET.get('search')
        if search_query:
            qs = qs.filter(Q(email__icontains=search_query) | Q(username__icontains=search_query) | Q(first_name__icontains=search_query) | Q(last_name__icontains=search_query))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        return context

class AdminUserActionView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def post(self, request, pk):
        from accounts.models import CustomUser
        from django.contrib import messages
        
        action = request.POST.get('action')
        user = CustomUser.objects.filter(pk=pk).exclude(role='ADMIN').first()
        
        if not user:
            messages.error(request, "User not found or cannot be modified.")
            return redirect('admin_users')
            
        if action == 'suspend':
            user.is_active = False
            user.save()
            messages.success(request, f"User {user.email} has been suspended.")
        elif action == 'activate':
            user.is_active = True
            user.save()
            messages.success(request, f"User {user.email} has been activated.")
        elif action == 'change_role':
            new_role = request.POST.get('new_role')
            if new_role in ['RECRUITER', 'CANDIDATE']:
                user.role = new_role
                user.save()
                messages.success(request, f"User {user.email}'s role updated to {new_role}.")
            else:
                messages.error(request, "Invalid role specified.")
        elif action == 'delete':
            email = user.email
            user.delete()
            messages.success(request, f"User {email} has been permanently deleted.")
        else:
            messages.error(request, "Invalid action.")
            
        redirect_url = request.META.get('HTTP_REFERER')
        if redirect_url:
            return redirect(redirect_url)
        return redirect('admin_users')

class AdminCategoryListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = 'dashboard/admin_categories.html'
    context_object_name = 'categories'

    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def get_queryset(self):
        from jobs.models import Category
        defaults = [
            'Software Development', 'AI/ML', 'Data Science', 'Cloud',
            'DevOps', 'Cyber Security', 'Testing', 'UI/UX'
        ]
        if not Category.objects.exists():
            for name in defaults:
                Category.objects.get_or_create(name=name, defaults={'is_active': True})
        return Category.objects.all().order_by('name')

class AdminCategoryToggleView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def post(self, request, pk):
        from jobs.models import Category
        from django.contrib import messages
        category = get_object_or_404(Category, pk=pk)
        category.is_active = not category.is_active
        category.save()
        status_str = "activated" if category.is_active else "deactivated"
        messages.success(request, f'Category "{category.name}" has been {status_str}.')
        return redirect('admin_categories')

class AdminCategoryCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    template_name = 'dashboard/admin_category_form.html'
    success_url = reverse_lazy('admin_categories')
    
    def get_queryset(self):
        from jobs.models import Category
        return Category.objects.all()

    @property
    def model(self):
        from jobs.models import Category
        return Category

    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def get_form_class(self):
        from jobs.forms import CategoryForm
        return CategoryForm

class AdminCategoryUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    template_name = 'dashboard/admin_category_form.html'
    success_url = reverse_lazy('admin_categories')
    
    def get_queryset(self):
        from jobs.models import Category
        return Category.objects.all()

    @property
    def model(self):
        from jobs.models import Category
        return Category

    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def get_form_class(self):
        from jobs.forms import CategoryForm
        return CategoryForm

class AdminCategoryDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    template_name = 'dashboard/admin_category_confirm_delete.html'
    success_url = reverse_lazy('admin_categories')

    def get_queryset(self):
        from jobs.models import Category
        return Category.objects.all()

    @property
    def model(self):
        from jobs.models import Category
        return Category

    def test_func(self):
        return self.request.user.role == 'ADMIN'

class AdminSystemConfigView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    template_name = 'dashboard/admin_system_config.html'
    success_url = reverse_lazy('admin_system_config')

    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def get_object(self, queryset=None):
        from .models import SystemConfiguration
        return SystemConfiguration.get_solo()

    def get_form_class(self):
        from .forms import SystemConfigurationForm
        return SystemConfigurationForm

    @property
    def model(self):
        from .models import SystemConfiguration
        return SystemConfiguration

class AdminAIConfigView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    template_name = 'dashboard/admin_ai_config.html'
    success_url = reverse_lazy('admin_ai_config')

    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def get_object(self, queryset=None):
        from .models import AIConfiguration
        return AIConfiguration.get_solo()

    def get_form_class(self):
        from .forms import AIConfigurationForm
        return AIConfigurationForm

    @property
    def model(self):
        from .models import AIConfiguration
        return AIConfiguration

class AdminAuditLogListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = 'dashboard/admin_audit_logs.html'
    context_object_name = 'logs'
    paginate_by = 50

    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def get_queryset(self):
        from .models import AuditLog
        from django.db.models import Q
        
        qs = AuditLog.objects.select_related('user').order_by('-timestamp')
        
        search_query = self.request.GET.get('search')
        if search_query:
            qs = qs.filter(
                Q(action__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(user__email__icontains=search_query) |
                Q(ip_address__icontains=search_query)
            )
            
        action_filter = self.request.GET.get('action')
        if action_filter:
            qs = qs.filter(action=action_filter)
            
        return qs

    def get_context_data(self, **kwargs):
        from .models import AuditLog
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['current_action'] = self.request.GET.get('action', '')
        # Get distinct actions for the filter dropdown
        context['actions'] = AuditLog.objects.values_list('action', flat=True).distinct().order_by('action')
        return context

class AdminBackupSecurityView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    template_name = 'dashboard/admin_backup_security.html'
    success_url = reverse_lazy('admin_backup_security')

    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def get_object(self, queryset=None):
        from .models import SecurityConfiguration
        return SecurityConfiguration.get_solo()

    def get_form_class(self):
        from .forms import SecurityConfigurationForm
        return SecurityConfigurationForm

    @property
    def model(self):
        from .models import SecurityConfiguration
        return SecurityConfiguration

class ExportDatabaseView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def post(self, request, *args, **kwargs):
        from django.core.management import call_command
        import io
        
        output = io.StringIO()
        try:
            call_command('dumpdata', format='json', indent=2, stdout=output, exclude=['contenttypes', 'auth.Permission'])
            json_data = output.getvalue()
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f"Failed to generate backup: {str(e)}")
            return redirect('admin_backup_security')
            
        response = HttpResponse(json_data, content_type='application/json')
        filename = f'database_backup_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


# ---------------------------------------------------------------------------
# PHASE 11: Analytics & Reporting Views
# ---------------------------------------------------------------------------

class AnalyticsDashboardView(LoginRequiredMixin, TemplateView):
    """
    Role-adaptive Analytics & Reporting dashboard view.
    Recruiter: Recruiter stats, hiring funnel, job analytics, AI analytics.
    Admin: Platform-wide stats, user breakdown, AI usage, activity timeline.
    Candidate: Personal stats & application status timeline (privacy guarded).
    """
    template_name = 'dashboard/analytics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        role = user.role

        context['user_role'] = role

        if role == 'CANDIDATE':
            context['candidate_analytics'] = AnalyticsService.get_candidate_analytics(user)
        elif role in ['RECRUITER', 'COMPANY']:
            recruiter_stats = AnalyticsService.get_recruiter_analytics(user)
            context['recruiter_analytics'] = recruiter_stats
            context['funnel'] = recruiter_stats.get('funnel', [])
            context['job_analytics'] = AnalyticsService.get_job_analytics(user)
            context['ai_analytics'] = AnalyticsService.get_ai_analytics(user)
        elif role == 'ADMIN':
            context['admin_analytics'] = AnalyticsService.get_admin_analytics()
            context['job_analytics'] = AnalyticsService.get_job_analytics(user)
            context['ai_analytics'] = AnalyticsService.get_ai_analytics(is_admin=True)

        return context


class AnalyticsAPIView(LoginRequiredMixin, View):
    """
    AJAX endpoint for retrieving JSON analytics metrics (e.g. per-job filter or refreshing stats).
    """
    def get(self, request):
        user = request.user
        role = user.role

        if role == 'CANDIDATE':
            data = AnalyticsService.get_candidate_analytics(user)
        elif role in ['RECRUITER', 'COMPANY']:
            job_id = request.GET.get('job_id')
            data = {
                'recruiter': AnalyticsService.get_recruiter_analytics(user),
                'job_analytics': AnalyticsService.get_job_analytics(user, job_id=int(job_id) if job_id and job_id.isdigit() else None),
                'ai_analytics': AnalyticsService.get_ai_analytics(user),
            }
        elif role == 'ADMIN':
            job_id = request.GET.get('job_id')
            data = {
                'admin': AnalyticsService.get_admin_analytics(),
                'job_analytics': AnalyticsService.get_job_analytics(user, job_id=int(job_id) if job_id and job_id.isdigit() else None),
                'ai_analytics': AnalyticsService.get_ai_analytics(is_admin=True),
            }
        else:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        return JsonResponse(data)


