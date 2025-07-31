from django.shortcuts import redirect  # Add this import
from django.http import HttpResponseForbidden
from threading import local
from .tenant_resolver import get_tenant_from_request
from .models import Tenant  # Add this import
import logging


logger = logging.getLogger(__name__)  # Add logger
_thread_local = local()

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # FIRST: Check if tenant is already set (from session)
        if not hasattr(request, 'tenant'):
            # Try to get tenant from session
            tenant_id = request.session.get('tenant_id')
            if tenant_id:
                try:
                    request.tenant = Tenant.objects.get(tenant_id=tenant_id)
                except Tenant.DoesNotExist:
                    pass
        
        # SECOND: If still not set, try request-based resolution
        if not hasattr(request, 'tenant'):
            request.tenant = get_tenant_from_request(request)
            logger.debug(f"Set tenant from request: {request.tenant.tenant_id if request.tenant else 'None'}")
        
        # THIRD: If still not set, try email-based resolution
        if not hasattr(request, 'tenant') and hasattr(request, 'user') and request.user.is_authenticated:
            email = getattr(request.user, 'email', '')
            if '@' in email:
                domain_part = email.split('@')[1]
                #tenant_id = domain_part.split('.')[0]
                tenant_id = domain_part  # change to use full domain name.
                try:
                    request.tenant = Tenant.objects.get(tenant_id=tenant_id)
                    logger.debug(f"Set tenant from email: {tenant_id}")
                except Tenant.DoesNotExist:
                    pass
        
        # Set thread-local DB
        if hasattr(request, 'tenant') and request.tenant:
            _thread_local.current_db = request.tenant.db_alias
            
            # ENFORCE TENANT ISOLATION
            if request.user.is_authenticated and not request.user.email.endswith('@master'):
                path = request.path_info
                if path.startswith('/tenant/'):
                    parts = path.split('/')
                    if len(parts) > 2:
                        url_tenant_id = parts[2]
                        if url_tenant_id != request.tenant.tenant_id:
                            logger.warning(
                                f"Tenant mismatch! User: {request.user.email} "
                                f"tried to access {url_tenant_id} "
                                f"but belongs to {request.tenant.tenant_id}"
                            )
                            # Redirect to correct tenant instead of error
                            return redirect(
                                'dashboard_app:dashboard', 
                                tenant_id=request.tenant.tenant_id
                            )
        else:
            _thread_local.current_db = 'default'
        
        response = self.get_response(request)
        return response
    
# Add to tenants/middleware.py
class BackendSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Inject session into auth backend
        from .backends import TenantAuthBackend
        if hasattr(request, 'session'):
            TenantAuthBackend.session = request.session
        
        return self.get_response(request)
    
class SecurityLoggerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        response = self.get_response(request)
        
        if hasattr(request, 'tenant') and request.tenant:
            return response
