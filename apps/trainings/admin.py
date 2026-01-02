"""
Admin configuration for Trainings models.
"""

from django.contrib import admin
from .models import Training, Video, UserProgress, UserTrainingReward


class VideoInline(admin.TabularInline):
    model = Video
    extra = 0
    fields = ['title', 'order', 'duration_seconds', 'is_active']


@admin.register(Training)
class TrainingAdmin(admin.ModelAdmin):
    list_display = ['title', 'company', 'is_active', 'is_mandatory', 'reward_points', 'total_videos', 'order']
    list_filter = ['is_active', 'is_mandatory', 'company']
    search_fields = ['title', 'description', 'company__name']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [VideoInline]
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ['title', 'training', 'duration_formatted', 'order', 'is_active']
    list_filter = ['is_active', 'training__company']
    search_fields = ['title', 'training__title']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(UserProgress)
class UserProgressAdmin(admin.ModelAdmin):
    list_display = ['user', 'video', 'progress_percentage', 'completed', 'completed_at']
    list_filter = ['completed', 'video__training__company']
    search_fields = ['user__email', 'video__title']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(UserTrainingReward)
class UserTrainingRewardAdmin(admin.ModelAdmin):
    list_display = ['user', 'training', 'points_earned', 'badge_earned', 'earned_at']
    list_filter = ['training__company', 'earned_at']
    search_fields = ['user__email', 'training__title']

