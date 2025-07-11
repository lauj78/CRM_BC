from django.urls import path
from . import views

app_name = 'dashboard_app'  # Define the namespace

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('upload/', views.upload_view, name='upload'),  # Optional, if you want a separate upload route
]