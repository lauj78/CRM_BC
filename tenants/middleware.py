#tenants/middleware.py

from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from .tenant_resolver import get_tenant_from_request
from .models import Tenant
from django.conf import settings
import logging
import uuid
# Import the shared context functions
from .context import set_current_db, get_current_db, clear_current_db

logger = logging.getLogger(__name__)


class TenantBypassMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        try:
            from django.urls import resolve
            resolved = resolve(request.path_info)
            view_func = resolved.func
            
            if hasattr(view_func, '_tenant_bypass'):
                request._skip_tenant_processing = True
                logger.debug(f"Detected tenant bypass for view: {resolved.url_name}")
        except Exception as e:
            logger.debug(f"View resolution error: {str(e)}")
            
        return self.get_response(request)

class BackendSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        if hasattr(request, '_backend_session_processed'):
            return self.get_response(request)
        request._backend_session_processed = True
        
        logger.debug(f"Entering BackendSessionMiddleware for path: {request.path}")
        try:
            from .backends import TenantAuthBackend
            if hasattr(request, 'session'):
                TenantAuthBackend.session = request.session
                logger.debug("Session injected into TenantAuthBackend")
        except Exception as e:
            logger.error(f"Error in BackendSessionMiddleware: {str(e)}")
        
        response = self.get_response(request)
        logger.debug(f"Exiting BackendSessionMiddleware with response: {type(response).__name__}")
        return response

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.master_dashboard_url = '/master/dashboard/'
        
    def __call__(self, request):
        if getattr(request, '_skip_tenant_processing', False):
            logger.debug(f"Skipping tenant processing for bypassed view: {request.path}")
            # Ensure the database context is set to default for bypassed views
            set_current_db('default')
            return self.get_response(request)
            
        public_paths = ['/accounts/', '/static/', '/favicon.ico', '/media/', '/master/']
        if any(request.path.startswith(p) for p in public_paths):
            logger.debug(f"Skipping tenant processing for public path: {request.path}")
            # Ensure default DB for public paths
            set_current_db('default')
            
            # Special check to ensure master user is redirected correctly
            if request.session.get('tenant_id') == 'master' and not request.path.startswith(self.master_dashboard_url):
                return redirect(self.master_dashboard_url)
                
            return self.get_response(request)
        
        if hasattr(request, '_tenant_middleware_processed'):
            return self.get_response(request)
        request._tenant_middleware_processed = True
        
        logger.debug(f"Entering TenantMiddleware for path: {request.path}")
        
        tenant_id = request.session.get('tenant_id')
        logger.debug(f"Session tenant_id: {tenant_id}")
        
        if tenant_id == 'master':
            logger.debug("Master user detected from session - skipping tenant resolution")
            set_current_db('default')
            logger.debug(f"Database set to: {get_current_db()} (master user)")
            
            # Master user should be redirected to their dedicated dashboard
            if not request.path.startswith(self.master_dashboard_url):
                logger.debug(f"Master user redirected to: {self.master_dashboard_url}")
                return redirect(self.master_dashboard_url)
            # The master user is on their correct path, so just proceed
            return self.get_response(request)

        # Tenant resolution logic
        if not hasattr(request, 'tenant'):
            if tenant_id:
                try:
                    request.tenant = Tenant.objects.using('default').get(tenant_id=tenant_id)
                    logger.debug(f"Tenant set from session: {request.tenant.tenant_id}")
                except Tenant.DoesNotExist:
                    logger.debug("Tenant from session does not exist")
                    pass
        
        if not hasattr(request, 'tenant'):
            from .tenant_resolver import get_tenant_from_request
            request.tenant = get_tenant_from_request(request)
            logger.debug(f"Set tenant from request: {request.tenant.tenant_id if request.tenant else 'None'}")
        
        if not hasattr(request, 'tenant') and hasattr(request, 'user') and request.user.is_authenticated:
            email = getattr(request.user, 'email', '')
            logger.debug(f"User email for resolution: {email}")
            if '@' in email:
                domain_part = email.split('@')[1]
                if domain_part != 'master.com':
                    tenant_id = domain_part
                    try:
                        request.tenant = Tenant.objects.using('default').get(tenant_id=tenant_id)
                        logger.debug(f"Set tenant from email: {tenant_id}")
                        request.session['tenant_id'] = domain_part
                    except Tenant.DoesNotExist:
                        logger.debug(f"Tenant not found for domain: {domain_part}")
                        pass
        
        if not hasattr(request, 'tenant') or not request.tenant:
            logger.debug("No tenant found - redirecting to login")
            set_current_db('default')
            return redirect(settings.LOGIN_URL)
        
        if hasattr(request, 'tenant') and request.tenant:
            set_current_db(request.tenant.db_alias)
            logger.debug(f"Database set to: {get_current_db()}")
            
            if request.user.is_authenticated and not request.user.email.endswith('@master.com'):
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
            set_current_db('default')
            logger.debug("No tenant found, using default database")
            
        try:
            response = self.get_response(request)
            logger.debug(f"Response from get_response: {type(response).__name__ if response else 'None'}")
        except Exception as e:
            logger.error(f"Exception in TenantMiddleware: {str(e)}")
            from django.http import HttpResponseServerError
            response = HttpResponseServerError("Server Error")
            
        # Important: Clean up thread-local context after request processing
        # Note: We don't clear here as other middleware might still need it
        logger.debug(f"Exiting TenantMiddleware with response: {type(response).__name__}")
        return response

class SecurityLoggerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        if hasattr(request, '_security_logger_processed'):
            return self.get_response(request)
        request._security_logger_processed = True
        
        middleware_id = uuid.uuid4().hex[:4]
        logger.debug(f"SecurityLoggerMiddleware START [{middleware_id}]")
        response = self.get_response(request)
        logger.debug(f"SecurityLoggerMiddleware END [{middleware_id}]")
        return response

class ResponseSafetyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        if hasattr(request, '_response_safety_processed'):
            return self.get_response(request)
        request._response_safety_processed = True
        
        logger.debug(f"Entering ResponseSafetyMiddleware for path: {request.path}")
        response = self.get_response(request)
        logger.debug(f"Received response: {type(response).__name__ if response else 'None'}")
        
        if response is None:
            logger.warning("Caught None response, returning HttpResponseServerError")
            from django.http import HttpResponseServerError
            return HttpResponseServerError("Invalid Response")
        
        logger.debug(f"Exiting ResponseSafetyMiddleware with response: {type(response).__name__}")
        
        # Clean up thread-local context at the very end of request processing
        clear_current_db()
        
        return response