"""
Admin configuration for Core models.
"""

from django.contrib import admin
from .models import Company, Role


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active', 'max_users', 'active_users_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'level', 'created_at']
    list_filter = ['level', 'company']
    search_fields = ['name', 'company__name']
    readonly_fields = ['created_at', 'updated_at']

