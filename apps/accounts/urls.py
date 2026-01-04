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
    path('profile/change-password/', views.change_password, name='change_password'),
    
    # Gestão de colaboradores (gestores)
    path('collaborators/', views.collaborators_list, name='collaborators_list'),
    path('collaborators/create/', views.collaborator_create, name='collaborator_create'),
    path('collaborators/<int:pk>/toggle/', views.collaborator_toggle_status, name='collaborator_toggle'),
]

