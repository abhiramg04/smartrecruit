from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, OTPRecord, ActivityLog

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'role', 'is_email_verified', 'is_staff']
    fieldsets = UserAdmin.fieldsets + (
        ('SmartRecruit Fields', {'fields': ('role', 'profile_photo', 'is_email_verified', 'bio')}),
    )

class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'ip_address', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('user__username', 'ip_address')

class OTPRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'otp_code', 'created_at', 'is_used')
    list_filter = ('is_used', 'created_at')

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(ActivityLog, ActivityLogAdmin)
admin.site.register(OTPRecord, OTPRecordAdmin)
