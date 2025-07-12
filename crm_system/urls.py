from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/data/login/', permanent=False)),
    path('data/', include('data_management.urls', namespace='data_management')),
    path('dashboard/', include('dashboard_app.urls', namespace='dashboard_app')),
    path('report/', include('report_app.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)