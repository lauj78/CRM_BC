from django.urls import path
from . import views

app_name = 'data_management'

urlpatterns = [
    path('upload/', views.upload_file, name='upload_file'),
    path('upload/success/', views.upload_success, name='upload_success'),
    path('upload/summary/', views.upload_summary, name='upload_summary'),
    path('download/errors/', views.download_errors, name='download_errors'),
    path('error-logs/', views.error_logs_list, name='error_logs_list'),
    # Remove tenant_id from these URLs since it's already captured in main urls.py
    path('error-logs/download/<int:log_id>/', views.download_log, name='download_log'),
    path('error-logs/delete/<int:log_id>/', views.delete_log, name='delete_log'),
    path('error-logs/bulk-delete/', views.bulk_delete_logs, name='bulk_delete_logs'),
]