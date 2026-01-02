"""
Admin configuration for Feedback models.
"""

from django.contrib import admin
from .models import FeedbackTicket, FeedbackComment


class FeedbackCommentInline(admin.TabularInline):
    model = FeedbackComment
    extra = 0
    readonly_fields = ['created_at']


@admin.register(FeedbackTicket)
class FeedbackTicketAdmin(admin.ModelAdmin):
    list_display = ['subject', 'user', 'company', 'sentiment', 'category', 'status', 'created_at']
    list_filter = ['status', 'sentiment', 'category', 'company', 'is_anonymous']
    search_fields = ['subject', 'message', 'user__email', 'company__name']
    inlines = [FeedbackCommentInline]
    readonly_fields = ['created_at', 'updated_at', 'responded_at']
    
    fieldsets = (
        ('Informações', {
            'fields': ('company', 'user', 'is_anonymous')
        }),
        ('Conteúdo', {
            'fields': ('sentiment', 'category', 'subject', 'message', 'attachment')
        }),
        ('Status', {
            'fields': ('status', 'response', 'responded_by', 'responded_at')
        }),
        ('Datas', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(FeedbackComment)
class FeedbackCommentAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'user', 'is_staff_reply', 'created_at']
    list_filter = ['is_staff_reply', 'ticket__company']
    search_fields = ['message', 'user__email']

