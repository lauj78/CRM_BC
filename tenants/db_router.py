# tenants/db_router.py
from django.conf import settings
import logging
from .context import get_current_db, has_db_context

logger = logging.getLogger(__name__)

class DatabaseTenantRouter:
    def db_for_read(self, model, **hints):
        return self._get_db(model, hints, operation="read")

    def db_for_write(self, model, **hints):
        return self._get_db(model, hints, operation="write")

    def _get_db(self, model, hints, operation):
        app_label = model._meta.app_label
        model_name = model._meta.model_name
        
        # Public apps (like auth, tenants) always use the 'default' DB.
        if app_label in settings.PUBLIC_APPS:
            logger.debug(f"{operation.upper()} for {app_label}.{model_name} -> default DB (public app)")
            return 'default'

        # If a thread-local database context is set, use it.
        if has_db_context():
            db_alias = get_current_db()
            logger.debug(f"{operation.upper()} for {app_label}.{model_name} -> tenant DB: {db_alias}")
            return db_alias
            
        # Fallback to default for everything else.
        logger.debug(f"{operation.upper()} for {app_label}.{model_name} -> default DB (no context)")
        return 'default'

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        PUBLIC_APPS = [
            'admin', 'auth', 'contenttypes', 'sessions', 'tenants', 'whatsapp_messaging'
        ]
        TENANT_APPS = [
            'data_management', 'dashboard_app', 'report_app', 'marketing_campaigns'
        ]
        
        if app_label in PUBLIC_APPS:
            # Public apps only migrate on default database
            return db == 'default'
        if app_label in TENANT_APPS:
            # Tenant apps only migrate on tenant databases (not default)
            return db != 'default'
        
        # For any other apps, allow migration on all databases
        return True