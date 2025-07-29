# tenants/backends.py
from django.contrib.auth import get_user_model
from .models import Tenant
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class TenantAuthBackend:
    def authenticate(self, request, username=None, password=None, **kwargs):
        logger.debug(f"Auth attempt: {username}")
        
        # Extract tenant ID from email
        if '@' not in username:
            logger.debug("Invalid email format")
            return None
            
        email_parts = username.split('@')
        if len(email_parts) != 2:
            logger.debug("Invalid email format")
            return None
            
        username_part = email_parts[0]
        domain_part = email_parts[1]
        tenant_id = domain_part.split('.')[0]
        
        logger.debug(f"Username: {username_part}, Tenant: {tenant_id}")
        
        # MASTER USER HANDLING
        if tenant_id == "master":
            try:
                user = User.objects.using('default').get(username=username_part)
                if user.check_password(password):
                    logger.debug("Master authentication SUCCESS")
                    request.session['tenant_id'] = 'master'
                    return user
                logger.debug("Invalid password for master")
            except User.DoesNotExist:
                logger.debug("Master user not found")
            return None
        
        # REGULAR TENANT HANDLING
        try:
            tenant = Tenant.objects.get(tenant_id=tenant_id)
            logger.debug(f"Found tenant: {tenant.name}")
        except Tenant.DoesNotExist:
            logger.debug(f"Tenant not found: {tenant_id}")
            return None
        
        try:
            user = User.objects.using(tenant.db_alias).get(username=username_part)
            if user.check_password(password):
                logger.debug("Authentication SUCCESS")
                # Store both tenant ID and database alias in session
                request.session['tenant_id'] = tenant.tenant_id
                request.session['tenant_db'] = tenant.db_alias
                return user
            logger.debug("Invalid password")
        except User.DoesNotExist:
            logger.debug(f"User not found: {username_part}")
        
        return None
    
    def get_user(self, user_id):
        """Retrieve user from session-stored database"""
        logger.debug(f"get_user called for ID: {user_id}")
        
        # First try to get from session-stored database
        try:
            db_alias = self.session.get('tenant_db', 'default')
            return User.objects.using(db_alias).get(pk=user_id)
        except (User.DoesNotExist, KeyError):
            logger.debug(f"User not found in session DB {db_alias}")
        
        # Fallback to scanning all databases
        for tenant in Tenant.objects.all():
            try:
                user = User.objects.using(tenant.db_alias).get(pk=user_id)
                logger.debug(f"Found user in {tenant.db_alias}")
                return user
            except User.DoesNotExist:
                continue
        
        # Finally try default database
        try:
            return User.objects.using('default').get(pk=user_id)
        except User.DoesNotExist:
            logger.debug(f"User {user_id} not found in any DB")
            return None