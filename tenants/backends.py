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
            # Use email as username (they're the same now)
            email = kwargs.get('email', username)
            logger.debug(f"Auth attempt: {email}")
            
            if not email or '@' not in email:
                logger.debug("Invalid email format")
                return None
                
            # MASTER USER HANDLING - check for master.com domain
            domain = email.split('@')[1]
            logger.debug(f"Extracted domain: {domain}")
            
            if domain == 'master.com':
                logger.debug("Master user detected (master.com domain)")
                try:
                    user = User.objects.using('default').get(username=email)  # Use username field
                    logger.debug(f"Found master user: {user.username}")
                    
                    if user.check_password(password):
                        logger.debug("Master password check passed")
                        if hasattr(request, 'session'):
                            request.session['tenant_id'] = 'master'
                            logger.debug("Session tenant_id set to: master")
                        return user
                    else:
                        logger.debug("Master password check failed")
                        return None
                        
                except User.DoesNotExist:
                    logger.debug("Master user not found in default database")
                    return None
                except Exception as e:
                    logger.error(f"Error accessing master user: {str(e)}")
                    return None
            
            # REGULAR TENANT HANDLING
            try:
                # Find tenant by domain
                tenant = Tenant.objects.using('default').get(tenant_id=domain)
                logger.debug(f"Found tenant: {tenant.name} (DB: {tenant.db_alias})")
            except Tenant.DoesNotExist:
                logger.debug(f"Tenant not found for domain: {domain}")
                return None
            except Exception as e:
                logger.error(f"Error finding tenant: {str(e)}")
                return None
            
            # Find user in tenant database
            try:
                logger.debug(f"Looking for user in database: {tenant.db_alias}")
                user = User.objects.using(tenant.db_alias).get(username=email)  # Use username field
                logger.debug(f"Found tenant user: {user.username} (active: {user.is_active})")
                
                if user.check_password(password):
                    logger.debug("Tenant password check passed")
                    if hasattr(request, 'session'):
                        request.session['tenant_id'] = tenant.tenant_id
                        logger.debug(f"Session tenant_id set to: {tenant.tenant_id}")
                    else:
                        logger.warning("No session available on request")
                    return user
                else:
                    logger.debug("Tenant password check failed")
                    return None
                    
            except User.DoesNotExist:
                logger.debug(f"User not found in tenant database: {tenant.db_alias}")
                return None
            except Exception as e:
                logger.error(f"Database error accessing {tenant.db_alias}: {str(e)}")
                return None
                
        except Exception as e:
            logger.error(f"Authentication exception: {str(e)}")
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
                if tenant_id == 'master':
                    # Master user in default database
                    try:
                        logger.debug(f"Looking for master user {user_id} in default DB")
                        return User.objects.using('default').get(pk=user_id)
                    except User.DoesNotExist:
                        logger.debug(f"Master user not found in default DB")
                        pass
                else:
                    # Regular tenant user
                    try:
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