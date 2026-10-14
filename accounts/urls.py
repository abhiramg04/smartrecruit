from django.urls import path, include
from .views import (
    UserLoginView, 
    UserLogoutView, 
    UserRegisterView, 
    CustomPasswordResetView,
    OTPVerifyView,
    ProfileUpdateView,
    CustomPasswordChangeView
)

urlpatterns = [
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    path('register/', UserRegisterView.as_view(), name='register'),
    path('verify-otp/', OTPVerifyView.as_view(), name='otp_verify'),
    path('profile/', ProfileUpdateView.as_view(), name='profile'),
    path('password-reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('password-change/', CustomPasswordChangeView.as_view(), name='password_change'),
    
    # API endpoints for JWT
    path('api/', include('accounts.api')),
]
