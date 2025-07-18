# dashboard_app/urls.py
from django.urls import path
from . import views

app_name = 'dashboard_app'

urlpatterns = [
    path('', views.dynamic_dashboard, name='dashboard'),
    path('upload/', views.upload_view, name='upload'),  # Optional, if you want a separate upload route
]