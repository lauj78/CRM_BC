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
        tenant_id = domain_part.split('.')[0]  # Get tenant from subdomain
        
        logger.debug(f"Username: {username_part}, Tenant: {tenant_id}")
        
        try:
            tenant = Tenant.objects.get(tenant_id=tenant_id)
            logger.debug(f"Found tenant: {tenant.name}")
        except Tenant.DoesNotExist:
            logger.debug(f"Tenant not found: {tenant_id}")
            return None
        
        # Authenticate using tenant database
        try:
            user = User.objects.using(tenant.db_alias).get(username=username_part)
            if user.check_password(password):
                logger.debug("Authentication SUCCESS")
                # Store tenant in session
                request.session['tenant_id'] = tenant.tenant_id
                request.session.save()  # Ensure session is saved immediately
                return user
            logger.debug("Invalid password")
        except User.DoesNotExist:
            logger.debug(f"User not found: {username_part}")
        
        return None
    
    def get_user(self, user_id):
        """CRITICAL FIX: Must return user object for session auth"""
        logger.debug(f"get_user called for ID: {user_id}")
        
        # Check all tenant databases
        for tenant in Tenant.objects.all():
            try:
                user = User.objects.using(tenant.db_alias).get(pk=user_id)
                logger.debug(f"Found user in {tenant.db_alias}")
                return user
            except User.DoesNotExist:
                continue
        
        logger.debug(f"User {user_id} not found in any tenant DB")
        return None