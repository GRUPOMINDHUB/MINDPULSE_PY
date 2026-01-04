"""
URLs para checklists.
"""

from django.urls import path
from . import views

app_name = 'checklists'

urlpatterns = [
    # Colaborador
    path('', views.checklist_list, name='list'),
    path('<int:pk>/', views.checklist_detail, name='detail'),
    
    # API
    path('api/task/<int:task_id>/toggle/', views.toggle_task, name='toggle_task'),
    path('api/task/<int:task_id>/delete/', views.task_delete, name='task_delete'),
    path('api/task/<int:task_id>/edit/', views.task_edit, name='task_edit'),
    path('api/checklist/<int:checklist_id>/task/create/', views.task_create_ajax, name='task_create_ajax'),
    path('api/users/', views.get_company_users, name='get_company_users'),
    
    # Gestão (Gestor + Admin Master)
    path('manage/', views.checklist_manage_list, name='manage_list'),
    path('manage/create/', views.checklist_create, name='create'),
    path('manage/<int:pk>/', views.checklist_manage_detail, name='manage_detail'),
    path('manage/<int:pk>/edit/', views.checklist_edit, name='edit'),
    path('manage/<int:pk>/delete/', views.checklist_delete, name='delete'),
]

