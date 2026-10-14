from rest_framework.permissions import BasePermission
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

# --- REST Framework API Permissions ---

class IsCandidate(BasePermission):
    """Allows access only to CANDIDATE users."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'CANDIDATE')

class IsRecruiter(BasePermission):
    """Allows access only to RECRUITER users."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'RECRUITER')

class IsAdminUserRole(BasePermission):
    """Allows access only to ADMIN users."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'ADMIN')


# --- Django Class-Based View Mixins ---

class CandidateRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Enforces authentication and CANDIDATE role for web views."""
    def test_func(self):
        return self.request.user.role == 'CANDIDATE'

class RecruiterRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Enforces authentication and RECRUITER role for web views."""
    def test_func(self):
        return self.request.user.role == 'RECRUITER'

class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Enforces authentication and ADMIN role for web views."""
    def test_func(self):
        return self.request.user.role == 'ADMIN'
