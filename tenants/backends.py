# tenants/backends.py
from django.contrib.auth import get_user_model
from .models import Tenant
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class TenantAuthBackend:
    session = None
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        email = kwargs.get('email', username)
        
        if not email or '@' not in email:
            return None
        
        domain = email.split('@')[1]
        
        try:
            if domain == 'master.com':
                user = User.objects.using('default').get(username=email)
                if user and user.check_password(password):
                    if hasattr(request, 'session'):
                        # --- CORRECTED LINE ---
                        # Set the session tenant_id to a simple string 'master'
                        request.session['tenant_id'] = 'master'
                    return user
            else:
                tenant = Tenant.objects.using('default').get(tenant_id=domain)
                user = User.objects.using(tenant.db_alias).get(username=email)

            if user and user.check_password(password):
                if hasattr(request, 'session'):
                    # For a tenant, the session ID is the domain
                    request.session['tenant_id'] = domain
                return user
        
        except (Tenant.DoesNotExist, User.DoesNotExist):
            pass
        except Exception as e:
            logger.error(f"Authentication exception: {str(e)}")
            
        return None
    
    def get_user(self, user_id):
        # This method's logic should already be correct based on previous conversations.
        # It correctly checks for the 'master' tenant ID.
        if tenant_id := getattr(self, 'session', {}).get('tenant_id'):
            if tenant_id == 'master':
                try:
                    return User.objects.using('default').get(pk=user_id)
                except User.DoesNotExist:
                    pass
            else:
                try:
                    tenant = Tenant.objects.using('default').get(tenant_id=tenant_id)
                    return User.objects.using(tenant.db_alias).get(pk=user_id)
                except (Tenant.DoesNotExist, User.DoesNotExist):
                    pass
        
        try:
            return User.objects.using('default').get(pk=user_id)
        except User.DoesNotExist:
            return None