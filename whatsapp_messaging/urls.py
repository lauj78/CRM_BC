#whatsapp_messaging/urls.py

from django.urls import path
from . import views

app_name = 'whatsapp_messaging'
urlpatterns = [
    # Main dashboard, CRUD for instances
    path('', views.dashboard, name='dashboard'),
    path('add/', views.add_instance, name='add_instance'),
    path('edit/<int:pk>/', views.edit_instance, name='edit_instance'),
    path('delete/<int:pk>/', views.delete_instance, name='delete_instance'),
    path('sync/', views.sync_instances, name='sync_instances'), 
    
    # Webhook endpoint for incoming messages from Evolution API
    path('webhooks/evolution/', views.webhook_handler, name='evolution_webhook'),
]
