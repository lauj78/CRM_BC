from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('', views.dashboard, name='dashboard'),  # Changed from 'dashboard/' to ''
    path('upload/', views.upload_view, name='upload'),
    path('logout/', views.logout_view, name='logout'),
]