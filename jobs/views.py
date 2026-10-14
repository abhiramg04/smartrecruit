from django.views.generic import CreateView, UpdateView, DeleteView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views import View
from .models import Job, Category
from .forms import JobForm
from dashboard.models import Notification

class JobListView(ListView):
    model = Job
    template_name = 'jobs/list.html'
    context_object_name = 'jobs'
    paginate_by = 10

    def get_queryset(self):
        qs = Job.objects.filter(is_approved=True, is_published=True, is_closed=False)
        
        # Search & Filters
        q = self.request.GET.get('q')
        cat = self.request.GET.get('category')
        work_model = self.request.GET.get('work_model')
        
        if q:
            qs = qs.filter(title__icontains=q)
        if cat:
            qs = qs.filter(category_id=cat)
        if work_model:
            qs = qs.filter(work_model=work_model)
            
        return qs.order_fields('-created_at') if hasattr(qs, 'order_fields') else qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context

class JobDetailView(DetailView):
    model = Job
    template_name = 'jobs/detail.html'
    context_object_name = 'job'

class JobCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Job
    form_class = JobForm
    template_name = 'jobs/form.html'
    success_url = reverse_lazy('company_job_list')

    def test_func(self):
        return self.request.user.role in ['COMPANY', 'RECRUITER']

    def form_valid(self, form):
        user = self.request.user
        company = getattr(user, 'owned_company', None) or getattr(user, 'company', None)

        if not company:
            from companies.models import Company
            company_name = f"{user.get_full_name() or user.username}'s Company"
            company, _ = Company.objects.get_or_create(
                owner=user,
                defaults={'name': company_name, 'is_approved': True}
            )
            user.company = company
            user.save()

        form.instance.company = company
        if company.is_approved:
            form.instance.is_approved = True

        # Handle Draft vs Publish
        action = self.request.POST.get('action', 'publish')
        if action == 'save_draft':
            form.instance.is_published = False
            messages.success(self.request, 'Job saved as DRAFT.')
        else:
            form.instance.is_published = True
            messages.success(self.request, 'Job posted successfully!')

        return super().form_valid(form)


    def form_invalid(self, form):
        messages.error(self.request, "Please correct the highlighted errors in the form below.")
        return super().form_invalid(form)


class JobUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Job
    form_class = JobForm
    template_name = 'jobs/form.html'
    
    def get_success_url(self):
        return reverse_lazy('job_detail', kwargs={'pk': self.object.pk})

    def test_func(self):
        job = self.get_object()
        if self.request.user.role == 'COMPANY' and hasattr(self.request.user, 'owned_company'):
            return job.company == self.request.user.owned_company
        elif self.request.user.role == 'RECRUITER':
            return job.company == self.request.user.company
        return False

    def form_valid(self, form):
        action = self.request.POST.get('action')
        if action == 'save_draft':
            form.instance.is_published = False
        elif action == 'publish':
            form.instance.is_published = True
        messages.success(self.request, 'Job updated successfully.')
        return super().form_valid(form)

class JobDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Job
    success_url = reverse_lazy('company_job_list')

    def test_func(self):
        job = self.get_object()
        if self.request.user.role == 'COMPANY' and hasattr(self.request.user, 'owned_company'):
            return job.company == self.request.user.owned_company
        elif self.request.user.role == 'RECRUITER':
            return job.company == self.request.user.company
        return False

class JobStatusToggleView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.role in ['COMPANY', 'RECRUITER']

    def post(self, request, pk, action):
        job = get_object_or_404(Job, pk=pk)
        
        # Verify ownership
        is_owner = False
        if self.request.user.role == 'COMPANY' and hasattr(self.request.user, 'owned_company') and job.company == self.request.user.owned_company:
            is_owner = True
        elif self.request.user.role == 'RECRUITER' and job.company == self.request.user.company:
            is_owner = True
            
        if not is_owner:
            messages.error(request, 'Permission denied.')
            return redirect('recruiter_dashboard')

        if action == 'publish':
            job.is_published = True
            job.is_closed = False
        elif action == 'unpublish' or action == 'draft':
            job.is_published = False
        elif action == 'close':
            job.is_closed = True
        elif action == 'open':
            job.is_closed = False
            job.is_published = True
            
        job.save()
        messages.success(request, f'Job status updated to {action}.')
        return redirect('job_detail', pk=job.pk)

class CompanyJobListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Job
    template_name = 'jobs/company_list.html'
    context_object_name = 'jobs'
    paginate_by = 20

    def test_func(self):
        return self.request.user.role in ['RECRUITER', 'COMPANY']

    def get_queryset(self):
        company = getattr(self.request.user, 'company', None)
        if not company and hasattr(self.request.user, 'owned_company'):
            company = self.request.user.owned_company

        qs = Job.objects.filter(company=company) if company else Job.objects.none()
        
        # Filtering
        status = self.request.GET.get('status')
        if status == 'active' or status == 'PUBLISHED':
            qs = qs.filter(is_published=True, is_closed=False)
        elif status == 'draft' or status == 'DRAFT':
            qs = qs.filter(is_published=False, is_closed=False)
        elif status == 'closed' or status == 'CLOSED':
            qs = qs.filter(is_closed=True)
            
        return qs.order_by('-created_at')

class JobApproveView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def post(self, request, pk):
        job = get_object_or_404(Job, pk=pk)
        job.is_approved = True
        job.save()
        # Notify company owner
        Notification.objects.create(
            user=job.company.owner,
            message=f'✅ Your job "{job.title}" has been approved and is now live for candidates to see.'
        )
        messages.success(request, f'Job "{job.title}" approved successfully.')
        return redirect('admin_approvals')


class JobRejectView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Admin rejects a pending job with an optional reason. Notifies the owner then deletes the job."""

    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def post(self, request, pk):
        job = get_object_or_404(Job, pk=pk)
        reason = request.POST.get('reason', '').strip()
        owner = job.company.owner
        job_title = job.title
        company_name = job.company.name

        msg = f'❌ Your job posting "{job_title}" for {company_name} was rejected by the admin.'
        if reason:
            msg += f' Reason: {reason}'

        Notification.objects.create(user=owner, message=msg)
        job.delete()
        messages.warning(request, f'Job "{job_title}" has been rejected and removed.')
        return redirect('admin_approvals')
