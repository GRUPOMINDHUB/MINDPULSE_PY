"""
URLs para feedback.
"""

from django.urls import path
from . import views

app_name = 'feedback'

urlpatterns = [
    # Colaborador
    path('', views.feedback_list, name='list'),
    path('create/', views.feedback_create, name='create'),
    path('<int:pk>/', views.feedback_detail, name='detail'),
    path('<int:pk>/delete/', views.feedback_delete, name='delete'),
    path('<int:pk>/comment/', views.add_comment, name='add_comment'),
    
    # Gestão (Gestor)
    path('manage/', views.feedback_manage_list, name='manage_list'),
    path('manage/<int:pk>/respond/', views.feedback_respond, name='respond'),
    path('manage/<int:pk>/status/', views.feedback_update_status, name='update_status'),
]

