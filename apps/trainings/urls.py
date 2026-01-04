"""
URLs para treinamentos.
"""

from django.urls import path
from . import views

app_name = 'trainings'

urlpatterns = [
    # Colaborador
    path('', views.training_list, name='list'),
    
    # Gestão (Gestor + Admin Master) - DEVE VIR ANTES DAS ROTAS GENÉRICAS
    path('manage/', views.training_manage_list, name='manage_list'),
    path('manage/create/', views.training_create, name='create'),
    path('manage/<int:pk>/', views.training_manage_detail, name='manage_detail'),
    path('manage/<int:pk>/edit/', views.training_edit, name='edit'),
    path('manage/<int:pk>/delete/', views.training_delete, name='delete'),
    
    # API
    path('api/progress/<int:video_id>/', views.update_progress, name='update_progress'),
    path('api/video/<int:video_id>/delete/', views.video_delete, name='video_delete'),
    path('api/videos/reorder/', views.video_reorder, name='video_reorder'),
    path('api/company-users/', views.get_company_users, name='get_company_users'),
    
    # Rotas genéricas (slug) - DEVEM VIR POR ÚLTIMO
    path('<slug:slug>/', views.training_detail, name='detail'),
    path('<slug:training_slug>/video/<int:video_id>/', views.video_player, name='player'),
]

