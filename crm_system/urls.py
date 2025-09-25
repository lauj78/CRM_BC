#crm_system/urls.py

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from tenants.views import tenant_test, tenant_redirect, account_locked
from django.contrib.auth.views import LoginView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', RedirectView.as_view(url='/accounts/login/', permanent=False)),
    path('tenant-test/', tenant_test),
    path('tenant-redirect/', tenant_redirect, name='tenant_redirect'),
    path('account-locked/', account_locked, name='account_locked'),
    
    # Master admin routes (no tenant)
    path('master/', include([
        path('dashboard/', include('dashboard_app.urls', namespace='master_dashboard')),
        path('Tenant Management/', include('tenant_management.urls', namespace='tenant_management')),
        #path('whatsapp/', include('whatsapp_messaging.urls', namespace='master_whatsapp')),
    ])),
    
    # Tenant-specific apps
    path('tenant/<tenant_id>/', include([
        path('data/', include('data_management.urls', namespace='data_management')),
        path('dashboard/', include('dashboard_app.urls', namespace='dashboard_app')),
        path('report/', include('report_app.urls', namespace='report_app')),
        path('whatsapp/', include('whatsapp_messaging.urls', namespace='whatsapp_messaging')),
        path('marketing/', include('marketing_campaigns.urls', namespace='marketing_campaigns')),
        path('tenant-test/', tenant_test),
    ])),
    
    
    # Global webhook endpoint (outside tenant context)
    path('api/whatsapp/', include('whatsapp_messaging.urls', namespace='api_whatsapp')),
    
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)