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
    path('manage/', views.manage_list, name='manage_list'),
    path('manage/create/', views.manage_create, name='create'),
    path('manage/<int:pk>/', views.manage_detail, name='manage_detail'),
    path('manage/<int:pk>/edit/', views.manage_edit, name='edit'),
    path('manage/<int:pk>/delete/', views.manage_delete, name='delete'),
    
    # Vídeos
    path('manage/<int:training_id>/video/create/', views.video_create, name='video_create'),
    path('manage/video/<int:video_id>/edit/', views.video_edit, name='video_edit'),
    path('manage/video/<int:video_id>/delete/', views.video_delete, name='video_delete'),
    
    # Quizzes
    path('manage/<int:training_id>/quiz/create/', views.quiz_create, name='quiz_create'),
    path('manage/quiz/<int:quiz_id>/edit/', views.quiz_edit, name='quiz_edit'),
    path('manage/quiz/<int:quiz_id>/delete/', views.quiz_delete, name='quiz_delete'),
    
    # API
    path('api/video/<int:video_id>/complete/', views.video_complete, name='video_complete'),
    path('api/content/reorder/<int:training_id>/', views.update_content_order, name='update_content_order'),
    path('api/training/<int:training_id>/status/', views.get_training_status, name='get_training_status'),
    
    # Quiz take
    path('<slug:slug>/quiz/<int:quiz_id>/take/', views.quiz_take, name='quiz_take'),
    
    # Rotas genéricas (slug) - DEVEM VIR POR ÚLTIMO
    path('<slug:slug>/', views.training_detail, name='detail'),
    path('<slug:slug>/content/<str:content_type>/<int:content_id>/', views.content_player, name='content_player'),
]
