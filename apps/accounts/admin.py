"""
Admin configuration for Accounts models.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserCompany, Warning


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'first_name', 'last_name', 'birth_date', 'is_active', 'total_points', 'last_activity']
    list_filter = ['is_active', 'is_staff', 'email_verified']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['email']
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Informações Pessoais', {'fields': ('first_name', 'last_name', 'phone', 'bio', 'avatar')}),
        ('Gamificação', {'fields': ('total_points',)}),
        ('Permissões', {'fields': ('is_active', 'is_staff', 'is_superuser', 'email_verified', 'groups', 'user_permissions')}),
        ('Datas', {'fields': ('last_login', 'last_activity', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )


@admin.register(UserCompany)
class UserCompanyAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'role', 'is_active', 'employee_id', 'joined_at']
    list_filter = ['is_active', 'company', 'role']
    search_fields = ['user__email', 'user__first_name', 'company__name', 'employee_id']
    raw_id_fields = ['user']
    readonly_fields = ['joined_at', 'deactivated_at']


@admin.register(Warning)
class WarningAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'warning_type', 'issuer', 'created_at']
    list_filter = ['warning_type', 'company', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'reason']
    raw_id_fields = ['user', 'issuer']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'

