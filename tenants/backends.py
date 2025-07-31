# tenants/backends.py
from django.contrib.auth import get_user_model
from .models import Tenant
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class TenantAuthBackend:
    session = None  # Class variable to store session
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        email = kwargs.get('email', username)
        logger.debug(f"Auth attempt: {email}")
        
        if not email or '@' not in email:
            return None
            
        try:
            # Store session for get_user
            self.session = request.session
            
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
                tenant = Tenant.objects.get(tenant_id=domain)
            except Tenant.DoesNotExist:
                return None
            
            user = User.objects.using(tenant.db_alias).get(email=email)
            if user.check_password(password):
                request.session['tenant_id'] = tenant.tenant_id
                return user
        except User.DoesNotExist:
            pass
        
        return None
    
    def get_user(self, user_id):
        """Retrieve user from all databases"""
        logger.debug(f"get_user called for ID: {user_id}")
    
        # First try to find user in the session's tenant database
        if tenant_id := self.session.get('tenant_id'):
            try:
                tenant = Tenant.objects.get(tenant_id=tenant_id)
                logger.debug(f"Looking for user {user_id} in tenant DB: {tenant.db_alias}")
                return User.objects.using(tenant.db_alias).get(pk=user_id)
            except (Tenant.DoesNotExist, User.DoesNotExist):
                logger.debug(f"User not found in tenant DB {tenant_id}")
                pass
    
        # Then try default database
        try:
            logger.debug(f"Looking for user {user_id} in default DB")
            return User.objects.using('default').get(pk=user_id)
        except User.DoesNotExist:
            logger.debug(f"User not found in default DB")
            pass
    
        # Then try all tenant databases
        for tenant in Tenant.objects.all():
            try:
                logger.debug(f"Looking for user {user_id} in DB {tenant.db_alias}")
                return User.objects.using(tenant.db_alias).get(pk=user_id)
            except User.DoesNotExist:
                continue
    
        logger.debug(f"User {user_id} not found in any DB")
        return None