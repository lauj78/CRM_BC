# marketing_campaigns/urls.py
from django.urls import path
from . import views

app_name = 'marketing_campaigns'

urlpatterns = [
    # Dashboard Home
    path('', views.dashboard_home, name='dashboard_home'),
    
    # Template Management
    path('templates/', views.templates_list, name='templates_list'),
    path('templates/create/', views.template_create, name='template_create'),
    path('templates/<int:pk>/edit/', views.template_edit, name='template_edit'),
    path('templates/<int:pk>/delete/', views.template_delete, name='template_delete'),
    path('templates/<int:pk>/preview/', views.template_preview, name='template_preview'),
    
    # Audience Management
    path('audiences/', views.audiences_list, name='audiences_list'),
    path('audiences/upload/', views.audience_upload, name='audience_upload'),
    path('audiences/<int:pk>/view/', views.audience_view, name='audience_view'),
    path('audiences/<int:pk>/edit/', views.audience_edit, name='audience_edit'),
    path('audiences/<int:pk>/delete/', views.audience_delete, name='audience_delete'),
    
    # Campaign Management - ADD THESE LINES
    path('campaigns/', views.campaigns_list, name='campaigns_list'),
    path('campaigns/create/', views.campaign_create, name='campaign_create'),
    path('campaigns/<int:pk>/', views.campaign_view, name='campaign_view'),
    path('campaigns/<int:pk>/edit/', views.campaign_edit, name='campaign_edit'),
    path('campaigns/<int:pk>/start/', views.campaign_start, name='campaign_start'),
    path('campaigns/<int:pk>/pause/', views.campaign_pause, name='campaign_pause'),
    path('campaigns/<int:pk>/delete/', views.campaign_delete, name='campaign_delete'),
]