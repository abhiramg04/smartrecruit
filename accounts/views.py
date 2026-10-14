from django.shortcuts import render, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView, FormView, UpdateView
from django.contrib.auth.views import LoginView, LogoutView, PasswordResetView, PasswordChangeView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from .forms import CustomUserCreationForm, OTPVerificationForm, UserProfileUpdateForm
from .models import CustomUser, OTPRecord, ActivityLog

class UserRegisterView(CreateView):
    form_class = CustomUserCreationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        user = form.save(commit=False)
        user.is_active = True           # Activate immediately — no OTP required
        user.is_email_verified = True   # Mark email as verified
        user.save()

        messages.success(
            self.request,
            f'Account created successfully! Welcome, {user.username}. Please log in to continue.'
        )
        return redirect('login')

class OTPVerifyView(FormView):
    template_name = 'accounts/otp_verify.html'
    form_class = OTPVerificationForm
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        user_id = self.request.session.get('pre_otp_user_id')
        if not user_id:
            messages.error(self.request, 'Session expired. Please register again.')
            return redirect('register')
            
        user = CustomUser.objects.get(id=user_id)
        otp = form.cleaned_data.get('otp')
        
        try:
            record = OTPRecord.objects.filter(user=user, otp_code=otp, is_used=False).latest('created_at')
            if record.is_valid():
                user.is_active = True
                user.is_email_verified = True
                user.save()
                record.is_used = True
                record.save()
                
                del self.request.session['pre_otp_user_id']
                messages.success(self.request, 'Email verified successfully! You can now login.')
                return super().form_valid(form)
            else:
                messages.error(self.request, 'OTP has expired or is invalid.')
                return self.form_invalid(form)
        except OTPRecord.DoesNotExist:
            messages.error(self.request, 'Invalid OTP.')
            return self.form_invalid(form)

class UserLoginView(LoginView):
    template_name = 'accounts/login.html'
    
    def form_valid(self, form):
        remember_me = self.request.POST.get('remember_me', False)
        if remember_me:
            self.request.session.set_expiry(1209600) # 2 weeks
        else:
            self.request.session.set_expiry(0) # Browser close
            
        response = super().form_valid(form)
        ActivityLog.objects.create(user=self.request.user, action='LOGIN', ip_address=self.request.META.get('REMOTE_ADDR'))
        return response
        
    def get_success_url(self):
        user = self.request.user
        if user.role == 'ADMIN':
            return reverse_lazy('admin_dashboard')
        elif user.role == 'RECRUITER':
            return reverse_lazy('recruiter_dashboard')
        else:
            return reverse_lazy('candidate_dashboard')

class UserLogoutView(LogoutView):
    next_page = reverse_lazy('login')
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            ActivityLog.objects.create(user=request.user, action='LOGOUT', ip_address=request.META.get('REMOTE_ADDR'))
        return super().dispatch(request, *args, **kwargs)

class CustomPasswordResetView(PasswordResetView):
    template_name = 'accounts/password_reset.html'
    success_url = reverse_lazy('login')
    
class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('profile')
    
    def form_valid(self, form):
        ActivityLog.objects.create(user=self.request.user, action='PASSWORD_CHANGE', ip_address=self.request.META.get('REMOTE_ADDR'))
        messages.success(self.request, 'Password changed successfully.')
        return super().form_valid(form)

from django.views import View

class ProfileUpdateView(LoginRequiredMixin, View):
    template_name = 'accounts/profile.html'

    def get(self, request):
        form = UserProfileUpdateForm(instance=request.user)
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = UserProfileUpdateForm(
            request.POST,
            request.FILES,
            instance=request.user
        )
        if form.is_valid():
            user = form.save(commit=False)
            # If no new photo was submitted, keep the existing one
            if 'profile_photo' not in request.FILES:
                user.profile_photo = request.user.profile_photo
            user.save()
            ActivityLog.objects.create(
                user=request.user,
                action='PROFILE_UPDATE',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
        else:
            # Show form errors clearly
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            return render(request, self.template_name, {'form': form})


