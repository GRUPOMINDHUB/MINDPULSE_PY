"""
Admin configuration for Checklists models.
"""

from django.contrib import admin
from .models import Checklist, Task, TaskDone, ChecklistCompletion


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0
    fields = ['title', 'order', 'is_required', 'is_active']


@admin.register(Checklist)
class ChecklistAdmin(admin.ModelAdmin):
    list_display = ['title', 'company', 'frequency', 'is_active', 'points_per_completion', 'total_tasks']
    list_filter = ['frequency', 'is_active', 'company']
    search_fields = ['title', 'description', 'company__name']
    inlines = [TaskInline]
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'checklist', 'order', 'is_required', 'is_active']
    list_filter = ['is_active', 'is_required', 'checklist__company']
    search_fields = ['title', 'checklist__title']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(TaskDone)
class TaskDoneAdmin(admin.ModelAdmin):
    list_display = ['user', 'task', 'period_key', 'completed_at']
    list_filter = ['period_key', 'task__checklist__company']
    search_fields = ['user__email', 'task__title']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ChecklistCompletion)
class ChecklistCompletionAdmin(admin.ModelAdmin):
    list_display = ['user', 'checklist', 'period_key', 'points_earned', 'completed_at']
    list_filter = ['checklist__company', 'period_key']
    search_fields = ['user__email', 'checklist__title']

