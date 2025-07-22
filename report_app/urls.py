# report_app/urls.py
from django.urls import path
from .views import report_hub_view

app_name = 'report_app'  # Add this line to define the app namespace

urlpatterns = [
    path('reports/', report_hub_view, name='report_hub'),
]