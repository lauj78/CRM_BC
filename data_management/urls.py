from django.urls import path
from .views import upload_file, upload_success, upload_summary, download_errors

urlpatterns = [
    path('upload/', upload_file, name='upload_file'),
    path('upload/success/', upload_success, name='upload_success'),
    path('upload/summary/', upload_summary, name='upload_summary'),
    path('upload/errors/download/', download_errors, name='download_errors'),
]