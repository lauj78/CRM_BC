from django.urls import path
from . import views

urlpatterns = [
    path('<str:report_name>/', views.report_view, name='report'),
]