from django.urls import path
from .views import (
    TenantListView, TenantUpdateView, TenantCreateView, TenantUserListView, TenantUserCreateView, TenantUserUpdateView, TenantUserPasswordView, AdminPasswordResetView
)

app_name = 'tenant_management'  # This sets the namespace

urlpatterns = [
    path('master/tenants/', TenantListView.as_view(), name='tenant_list'),
    path('master/tenants/create/', TenantCreateView.as_view(), name='create_tenant'),
    path('master/tenants/<int:pk>/edit/', TenantUpdateView.as_view(), name='edit_tenant'),
    path('master/tenants/<int:tenant_id>/users/<int:pk>/password/', TenantUserPasswordView.as_view(), name='change_password'),
    path('master/tenants/<int:tenant_id>/users/<int:pk>/reset_password/', AdminPasswordResetView.as_view(), name='reset_password'),
    
    path('master/tenants/<int:tenant_id>/users/', 
         TenantUserListView.as_view(), name='manage_users'),
    path('master/tenants/<int:tenant_id>/users/create/', 
         TenantUserCreateView.as_view(), name='create_user'),
    path('master/tenants/<int:tenant_id>/users/<int:pk>/edit/', 
         TenantUserUpdateView.as_view(), name='edit_user'),
]