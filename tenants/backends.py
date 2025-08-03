# tenants/backends.py
from django.contrib.auth import get_user_model
from .models import Tenant
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class TenantAuthBackend:
    session = None
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        # Add recursion prevention
        if hasattr(request, '_auth_in_progress'):
            logger.debug("Authentication already in progress")
            return None
            
        request._auth_in_progress = True
        logger.debug(f"Auth started for request: {id(request)}")
        
        try:
            email = kwargs.get('email', username)
            logger.debug(f"Auth attempt: {email}")
            
            if not email or '@' not in email:
                return None
                
            # MASTER USER HANDLING
            if email.endswith('@master'):
                user = User.objects.using('default').get(email=email)
                if user.check_password(password):
                    request.session['tenant_id'] = 'master'
                    return user
                return None
            
            # REGULAR TENANT HANDLING
            domain = email.split('@')[1]
            try:
                # Use default DB for tenant lookup
                tenant = Tenant.objects.using('default').get(tenant_id=domain)
            except Tenant.DoesNotExist:
                return None
            
            user = User.objects.using(tenant.db_alias).get(email=email)
            if user.check_password(password):
                request.session['tenant_id'] = tenant.tenant_id
                return user
                
            return None
        finally:
            if hasattr(request, '_auth_in_progress'):
                del request._auth_in_progress
            logger.debug(f"Auth completed for request: {id(request)}")
    
    def get_user(self, user_id):
        """Lightweight user retrieval without tenant queries"""
        # Add recursion prevention
        if hasattr(self, '_get_user_in_progress'):
            logger.debug("Prevented recursive get_user call")
            return None
            
        self._get_user_in_progress = True
        logger.debug(f"get_user called for ID: {user_id}")
        
        try:
            # Try session tenant first
            if tenant_id := getattr(self, 'session', {}).get('tenant_id'):
                try:
                    # Use default DB for tenant lookup
                    tenant = Tenant.objects.using('default').get(tenant_id=tenant_id)
                    logger.debug(f"Looking for user {user_id} in tenant DB: {tenant.db_alias}")
                    return User.objects.using(tenant.db_alias).get(pk=user_id)
                except (Tenant.DoesNotExist, User.DoesNotExist) as e:
                    logger.debug(f"User not found in tenant DB: {str(e)}")
                    pass
            
            # Fallback to default database
            try:
                logger.debug(f"Looking for user {user_id} in default DB")
                return User.objects.using('default').get(pk=user_id)
            except User.DoesNotExist:
                logger.debug(f"User not found in default DB")
                return None
        finally:
            del self._get_user_in_progress