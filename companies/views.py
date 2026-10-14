from django.views.generic import CreateView, UpdateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from .models import Company, Department
from .forms import CompanyForm
from applications.models import Application
from dashboard.models import Notification


class CompanyCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Company
    form_class = CompanyForm
    template_name = 'companies/create_update.html'
    success_url = reverse_lazy('company_profile')

    def test_func(self):
        return self.request.user.role == 'RECRUITER' and not (hasattr(self.request.user, 'owned_company') or self.request.user.company)

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        # Link user to company
        self.request.user.company = self.object
        self.request.user.save()
        messages.success(self.request, 'Company profile created successfully! It is pending admin approval.')
        return response


class CompanyUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Company
    form_class = CompanyForm
    template_name = 'companies/create_update.html'
    success_url = reverse_lazy('company_profile')

    def test_func(self):
        company = self.get_object()
        return self.request.user.role == 'RECRUITER' and (self.request.user == company.owner or self.request.user.company == company)

    def form_valid(self, form):
        messages.success(self.request, 'Company profile updated successfully.')
        return super().form_valid(form)


class CompanyDetailView(LoginRequiredMixin, DetailView):
    model = Company
    template_name = 'companies/detail.html'
    context_object_name = 'company'


class CompanyProfileView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.role == 'RECRUITER'

    def get_company(self, request):
        if hasattr(request.user, 'owned_company'):
            return request.user.owned_company
        return request.user.company

    def get(self, request):
        company = self.get_company(request)
        if not company:
            messages.info(request, 'Please create your company profile to get started.')
            return redirect('company_create')
            
        from jobs.models import Job
        jobs = Job.objects.filter(company=company)
        active_jobs_count = jobs.filter(is_published=True, is_closed=False).count()
        total_applications = Application.objects.filter(job__company=company).count()
        context = {
            'company': company,
            'active_jobs_count': active_jobs_count,
            'total_applications': total_applications,
            'departments_count': company.departments.count(),
        }
        return render(request, 'companies/profile.html', context)

    def post(self, request):
        company = self.get_company(request)
        action = request.POST.get('action')
        user = request.user

        if action == 'update_info':
            # Update Recruiter Personal Info
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            email = request.POST.get('email')
            phone = request.POST.get('phone')
            designation = request.POST.get('designation')

            if first_name is not None: user.first_name = first_name
            if last_name is not None: user.last_name = last_name
            if email is not None: user.email = email
            if phone is not None: user.phone = phone
            if designation is not None: user.designation = designation
            user.save()

            # Update Company Info
            if company:
                company.name = request.POST.get('name', company.name)
                company.industry = request.POST.get('industry', company.industry)
                company.location = request.POST.get('location', company.location)
                company.website = request.POST.get('website', company.website)
                company.description = request.POST.get('description', company.description)
                company.save()

            messages.success(request, 'Recruiter & Company profile updated successfully.')

        elif action == 'add_dept' and company:
            dept_name = request.POST.get('dept_name')
            dept_desc = request.POST.get('dept_description')
            if dept_name:
                Department.objects.create(
                    company=company,
                    name=dept_name,
                    description=dept_desc
                )
                messages.success(request, f'Department "{dept_name}" added.')

        elif action == 'delete_dept' and company:
            dept_id = request.POST.get('dept_id')
            dept = get_object_or_404(Department, id=dept_id, company=company)
            dept_name = dept.name
            dept.delete()
            messages.success(request, f'Department "{dept_name}" removed.')

        return redirect('company_profile')


class CompanyApproveView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Admin approves a pending company. Notifies the owner."""

    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def post(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        company.is_approved = True
        company.save()
        Notification.objects.create(
            user=company.owner,
            message=f'🎉 Congratulations! Your company "{company.name}" has been approved. You can now post jobs.'
        )
        messages.success(request, f'Company "{company.name}" approved successfully.')
        return redirect('admin_approvals')


class CompanyRejectView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Admin rejects a pending company, optionally with a reason. Notifies the owner then deletes the record."""

    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def post(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        reason = request.POST.get('reason', '').strip()
        owner = company.owner
        company_name = company.name

        msg = f'❌ Your company "{company_name}" registration was rejected.'
        if reason:
            msg += f' Reason: {reason}'

        Notification.objects.create(user=owner, message=msg)
        company.delete()
        messages.warning(request, f'Company "{company_name}" has been rejected and removed.')
        return redirect('admin_approvals')
