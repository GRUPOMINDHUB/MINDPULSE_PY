"""
URLs de autenticação e gestão de usuários.
"""

from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('configuracoes/', views.settings_view, name='settings'),
    
    # Gestão de colaboradores (gestores)
    path('collaborators/', views.collaborators_list, name='collaborators_list'),
    path('collaborators/create/', views.collaborator_create, name='collaborator_create'),
    path('collaborators/<int:pk>/toggle/', views.collaborator_toggle_status, name='collaborator_toggle'),
    
    # Advertências disciplinares (gestores e admin master)
    path('warnings/', views.warning_list, name='warning_list'),
    path('warnings/create/', views.warning_create, name='warning_create'),
]

