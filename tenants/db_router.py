from threading import local
from django.conf import settings

_thread_local = local()

class DatabaseTenantRouter:
    def db_for_read(self, model, **hints):
        return self._get_db(model, hints)

    def db_for_write(self, model, **hints):
        return self._get_db(model, hints)

    def _get_db(self, model, hints):
        # Public models (tenants app) always use default DB
        if model._meta.app_label == 'tenants':
            return 'default'
            
        # Tenant-specific models
        if hasattr(_thread_local, 'current_db'):
            return _thread_local.current_db
            
        # Fallback to default
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
            return True
            
        # Tenant apps should only be in tenant databases
        if app_label in TENANT_APPS:
            return db != 'default'
            
        # Default allow for other apps
        return True