from django.urls import path
from .views import upload_file, upload_success, upload_summary, download_errors, error_logs_list, download_log, delete_log

urlpatterns = [
    path('upload/', upload_file, name='upload_file'),
    path('upload/success/', upload_success, name='upload_success'),
    path('upload/summary/', upload_summary, name='upload_summary'),
    path('upload/errors/download/', download_errors, name='download_errors'),
    path('error-logs/', error_logs_list, name='error_logs_list'),
    path('error-logs/download/<int:log_id>/', download_log, name='download_log'),
    path('error-logs/delete/<int:log_id>/', delete_log, name='delete_log'),
]