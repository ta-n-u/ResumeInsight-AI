# core/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, JobDescription, Candidate, Resume, MatchResult, Skill, Notification


# -------------------------------------------------------------------
# Custom User Admin
# -------------------------------------------------------------------
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display  = ('username', 'email', 'role', 'is_staff', 'is_active')
    list_filter   = ('role', 'is_staff', 'is_active')
    fieldsets     = UserAdmin.fieldsets + (
        ('ResumeInsight Role', {'fields': ('role', 'profile_picture')}),
    )


# -------------------------------------------------------------------
# Register all other models
# -------------------------------------------------------------------
@admin.register(JobDescription)
class JobDescriptionAdmin(admin.ModelAdmin):
    list_display  = ('title', 'department', 'status', 'created_by', 'created_at')
    list_filter   = ('status', 'department')
    search_fields = ('title', 'department')


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display  = ('full_name', 'email', 'blind_id', 'uploaded_by', 'created_at')
    search_fields = ('full_name', 'email', 'blind_id')


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display  = ('candidate', 'job', 'is_processed', 'uploaded_at')
    list_filter   = ('is_processed',)


@admin.register(MatchResult)
class MatchResultAdmin(admin.ModelAdmin):
    list_display  = ('candidate', 'job', 'match_percentage', 'rank', 'created_at')
    list_filter   = ('job',)
    ordering      = ('-match_percentage',)


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display  = ('name', 'category', 'added_by', 'created_at')
    list_filter   = ('category',)
    search_fields = ('name',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display  = ('user', 'message', 'is_read', 'created_at')
    list_filter   = ('is_read',)
