# tenants/signals.py
from django.contrib.auth.signals import user_logged_in
from django.utils import timezone
from .models import Tenant
import logging

logger = logging.getLogger(__name__)

# Note: We are removing the @receiver decorator here
def update_last_login_with_tenant_db(sender, request, user, **kwargs):
    """
    Updates the last_login field for a user, using the correct tenant database.
    This handler explicitly specifies the database to bypass the router issues.
    """
    if not hasattr(user, 'email') or '@' not in user.email:
        return

    email = user.email
    domain = email.split('@')[1]
    db_alias = 'default'

    if domain != 'master.com':
        try:
            tenant = Tenant.objects.using('default').get(tenant_id=domain)
            db_alias = tenant.db_alias
        except Tenant.DoesNotExist:
            logger.error(f"Tenant not found for domain {domain}. Cannot update last_login.")
            return

    # Set the user's last_login timestamp
    user.last_login = timezone.now()

    try:
        # Crucial step: We explicitly tell Django which database to save to.
        user.save(update_fields=["last_login"], using=db_alias)
        logger.debug(f"Successfully updated last_login for user {user.username} in database {db_alias}.")
    except Exception as e:
        logger.error(f"Failed to update last_login for user {user.username} in database {db_alias}: {e}")