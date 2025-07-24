# dashboard_app/urls.py
from django.urls import path
from . import views

app_name = 'dashboard_app'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    # Other paths if any
]