from django.contrib import admin
from .models import Assessment, Question, AssessmentAssignment, AssessmentResult

@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_by', 'job', 'duration_minutes', 'pass_percentage', 'created_at')
    search_fields = ('title', 'description')

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('assessment', 'question_type', 'text', 'marks')
    list_filter = ('question_type',)

@admin.register(AssessmentAssignment)
class AssessmentAssignmentAdmin(admin.ModelAdmin):
    list_display = ('application', 'assessment', 'assigned_at', 'status')

@admin.register(AssessmentResult)
class AssessmentResultAdmin(admin.ModelAdmin):
    list_display = ('application', 'assessment', 'final_score', 'is_passed', 'time_submitted', 'duration_seconds')

