"""
Core URLs - Dashboard e páginas principais
"""

from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    
    # Dashboards por nível de acesso
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/gestor/', views.gestor_dashboard, name='gestor_dashboard'),
    path('dashboard/colaborador/', views.colaborador_dashboard, name='colaborador_dashboard'),
    
    # Gestão de Empresas (Admin)
    path('empresas/', views.company_list, name='company_list'),
    path('empresas/nova/', views.company_create, name='company_create'),
    path('empresas/<int:pk>/', views.company_detail, name='company_detail'),
    path('empresas/<int:pk>/editar/', views.company_edit, name='company_edit'),
    path('empresas/<int:pk>/usuarios/', views.company_users, name='company_users'),
    path('empresas/<int:pk>/usuarios/novo/', views.company_add_user, name='company_add_user'),
    
    # Troca de empresa (Admin Master)
    path('switch-company/', views.switch_company, name='switch_company'),
    
    # Relatórios (Gestor | Admin Master)
    path('relatorios/', views.report_management, name='report_management'),
]

