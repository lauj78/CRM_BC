# tenants/apps.py
from django.apps import AppConfig

class TenantsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tenants'

    def ready(self):
        # We must perform this import inside ready() to avoid AppRegistryNotReady errors.
        from django.contrib.auth.models import update_last_login
        from django.contrib.auth.signals import user_logged_in
        from .signals import update_last_login_with_tenant_db

        # Step 1: Monkey-patch the built-in signal handler function to be a no-op.
        # This is a final measure to ensure it never runs, even if connected.
        update_last_login.__code__ = (lambda *args, **kwargs: None).__code__
        print("Monkey-patched Django's built-in update_last_login signal handler to do nothing.")

        # Step 2: Connect our custom signal handler.
        # We must manually disconnect first to avoid connecting it twice if the server reloads.
        user_logged_in.disconnect(update_last_login_with_tenant_db)
        user_logged_in.connect(update_last_login_with_tenant_db)
        print("Connected our custom update_last_login signal handler.")