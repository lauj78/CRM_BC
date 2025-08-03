# tenants/db_router.py
from threading import local
from django.conf import settings
import logging

logger = logging.getLogger(__name__)
_thread_local = local()

class DatabaseTenantRouter:
    def db_for_read(self, model, **hints):
        return self._get_db(model, hints, operation="read")

    def db_for_write(self, model, **hints):
        return self._get_db(model, hints, operation="write")

    def _get_db(self, model, hints, operation):
        app_label = model._meta.app_label
        model_name = model._meta.model_name
        base_log = f"{operation.upper()} for {app_label}.{model_name}"
        
        # Public models (tenants app) always use default DB
        if app_label == 'tenants':
            logger.debug(f"{base_log} → default DB (tenants app)")
            return 'default'
            
        # Tenant-specific models
        if hasattr(_thread_local, 'current_db'):
            db_alias = _thread_local.current_db
            logger.debug(f"{base_log} → tenant DB: {db_alias}")
            return db_alias
            
        # Fallback to default
        logger.debug(f"{base_log} → default DB (no current_db)")
        return 'default'

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # PUBLIC APPS: Should be in both databases
        PUBLIC_APPS = [
            'admin',
            'auth',
            'contenttypes',
            'sessions',
            'tenants'
        ]
        
        # TENANT APPS: Should only be in tenant databases
        TENANT_APPS = [
            'data_management',
            'dashboard_app',
            'report_app'
        ]
        
        # Public apps should be in both databases
        if app_label in PUBLIC_APPS:
            logger.debug(f"Migrate {app_label} allowed in {db} (public app)")
            return True
            
        # Tenant apps should only be in tenant databases
        if app_label in TENANT_APPS:
            allowed = (db != 'default')
            logger.debug(f"Migrate {app_label} in {db}: {'ALLOWED' if allowed else 'DENIED'} (tenant app)")
            return allowed
            
        # Default allow for other apps
        logger.debug(f"Migrate {app_label} in {db}: ALLOWED (default)")
        return True