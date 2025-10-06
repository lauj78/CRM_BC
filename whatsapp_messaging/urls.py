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
    path('<int:pk>/qr-code/', views.get_qr_code, name='get_qr_code'),  # Add this
    path('<int:pk>/send-message/', views.send_test_message, name='send_message'),  # Add this

    path('anti-ban-settings/', views.anti_ban_settings, name='anti_ban_settings'),

    # Webhook endpoint for incoming messages from Evolution API
    path('webhooks/evolution/', views.webhook_handler, name='evolution_webhook'),
]
