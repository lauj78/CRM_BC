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
        # Get app classifications from settings
        public_apps = getattr(settings, 'PUBLIC_APPS', [])
        tenant_apps = getattr(settings, 'TENANT_APPS', [])
        
        if app_label in public_apps:
            # Public apps only migrate on default database
            allow = db == 'default'
            logger.debug(f"Migration {app_label} on {db}: {'ALLOWED' if allow else 'BLOCKED'} (public app)")
            return allow
            
        if app_label in tenant_apps:
            # Tenant apps only migrate on tenant databases (not default)
            allow = db != 'default'
            logger.debug(f"Migration {app_label} on {db}: {'ALLOWED' if allow else 'BLOCKED'} (tenant app)")
            return allow
        
        # For Django core apps, allow migration on all databases
        django_core_apps = ['admin', 'auth', 'contenttypes', 'sessions', 'django_celery_beat', 'django_celery_results']
        if app_label in django_core_apps:
            allow = True
            logger.debug(f"Migration {app_label} on {db}: ALLOWED (django core)")
            return allow
        
        # Default: allow migration everywhere
        logger.debug(f"Migration {app_label} on {db}: ALLOWED (default)")
        return True