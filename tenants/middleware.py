from django.shortcuts import redirect  # Add this import
from django.http import HttpResponseForbidden
from threading import local
from .tenant_resolver import get_tenant_from_request
from .models import Tenant  # Add this import
from django.conf import settings  # Add this import
import logging


logger = logging.getLogger(__name__)  # Add logger
_thread_local = local()

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # ADDED: Skip tenant processing for public paths
        public_paths = ['/accounts/', '/static/', '/favicon.ico', '/media/']
        if any(request.path.startswith(p) for p in public_paths):
            logger.debug(f"Skipping tenant processing for public path: {request.path}")
            return self.get_response(request)
        
        logger.debug(f"Entering TenantMiddleware for path: {request.path}")
        
        # Existing tenant resolution logic
        if not hasattr(request, 'tenant'):
            tenant_id = request.session.get('tenant_id')
            logger.debug(f"Session tenant_id: {tenant_id}")
            if tenant_id:
                try:
                    request.tenant = Tenant.objects.get(tenant_id=tenant_id)
                    logger.debug(f"Tenant set from session: {request.tenant.tenant_id}")
                except Tenant.DoesNotExist:
                    logger.debug("Tenant from session does not exist")
                    pass
        
        if not hasattr(request, 'tenant'):
            request.tenant = get_tenant_from_request(request)
            logger.debug(f"Set tenant from request: {request.tenant.tenant_id if request.tenant else 'None'}")
        
        if not hasattr(request, 'tenant') and hasattr(request, 'user') and request.user.is_authenticated:
            email = getattr(request.user, 'email', '')
            logger.debug(f"User email for resolution: {email}")
            if '@' in email:
                domain_part = email.split('@')[1]
                tenant_id = domain_part
                try:
                    request.tenant = Tenant.objects.get(tenant_id=tenant_id)
                    logger.debug(f"Set tenant from email: {tenant_id}")
                except Tenant.DoesNotExist:
                    logger.debug(f"Tenant not found for domain: {domain_part}")
                    pass
        
        # ADDED: Redirect to login if no tenant found (for non-public paths)
        if not hasattr(request, 'tenant') or not request.tenant:
            logger.debug("No tenant found - redirecting to login")
            return redirect(settings.LOGIN_URL)
        
        # Existing database and isolation logic
        if hasattr(request, 'tenant') and request.tenant:
            _thread_local.current_db = request.tenant.db_alias
            logger.debug(f"Database set to: {_thread_local.current_db}")
            
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
                            return redirect(
                                'dashboard_app:dashboard', 
                                tenant_id=request.tenant.tenant_id
                            )
        else:
            _thread_local.current_db = 'default'
            logger.debug("No tenant found, using default database")
            
        try:
            response = self.get_response(request)
            logger.debug(f"Response from get_response: {type(response).__name__ if response else 'None'}")
        except Exception as e:
            logger.error(f"Exception in TenantMiddleware: {str(e)}")
            from django.http import HttpResponseServerError
            response = HttpResponseServerError("Server Error")
            
        logger.debug(f"Exiting TenantMiddleware with response: {type(response).__name__}")
        return response
    
# Add to tenants/middleware.py
class BackendSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Inject session into auth backend
        logger.debug(f"Entering BackendSessionMiddleware for path: {request.path}")
        try:
            from .backends import TenantAuthBackend
            if hasattr(request, 'session'):
                TenantAuthBackend.session = request.session
                logger.debug("Session injected into TenantAuthBackend")
        except Exception as e:
            logger.error(f"Error in BackendSessionMiddleware: {str(e)}")
            pass  # Don't break the middleware chain
        
        # ALWAYS RETURN A RESPONSE
        response = self.get_response(request)
        logger.debug(f"Exiting BackendSessionMiddleware with response: {type(response).__name__ if response else 'None'}")
        return response
    
class SecurityLoggerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        logger.debug(f"Entering SecurityLoggerMiddleware for path: {request.path}")
        response = self.get_response(request)
        logger.debug(f"Exiting SecurityLoggerMiddleware with response: {type(response).__name__}")
        return response  # ALWAYS return response
        
    #    if hasattr(request, 'tenant') and request.tenant:
    #        logger.debug(f"Security check passed for tenant: {request.tenant.tenant_id}")
    #        return response


class ResponseSafetyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        logger.debug(f"Entering ResponseSafetyMiddleware for path: {request.path}")
        response = self.get_response(request)
        logger.debug(f"Received response: {type(response).__name__ if response else 'None'}")
        
        if response is None:
            logger.warning("Caught None response, returning HttpResponseServerError")
            from django.http import HttpResponseServerError
            return HttpResponseServerError("Invalid Response")
        
        logger.debug(f"Exiting ResponseSafetyMiddleware with response: {type(response).__name__}")
        return response