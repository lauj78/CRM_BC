# marketing_campaigns/urls.py - TEMPLATES ONLY (Phase 1)
from django.urls import path
from . import views

app_name = 'marketing_campaigns'

urlpatterns = [
    # Dashboard Home (temporary)
    path('', views.dashboard_home, name='dashboard_home'),
    
    # Template Management
    path('templates/', views.templates_list, name='templates_list'),
    path('templates/create/', views.template_create, name='template_create'),
    path('templates/<int:pk>/edit/', views.template_edit, name='template_edit'),
    path('templates/<int:pk>/delete/', views.template_delete, name='template_delete'),
    path('templates/<int:pk>/preview/', views.template_preview, name='template_preview'),
    path('audiences/', views.audiences_list, name='audiences_list'),
    path('audiences/upload/', views.audience_upload, name='audience_upload'),
    path('audiences/<int:pk>/view/', views.audience_view, name='audience_view'),
    path('audiences/<int:pk>/delete/', views.audience_delete, name='audience_delete'),
    path('audiences/<int:pk>/edit/', views.audience_edit, name='audience_edit'),
]