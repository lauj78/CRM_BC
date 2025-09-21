import os
from django.core.management.base import BaseCommand
from django.core.management import call_command
from tenants.models import Tenant # Your existing Tenant model

class Command(BaseCommand):
    help = 'Runs migrations for the whatsapp_messaging app on all tenant databases.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- Starting multi-tenant migration for 'whatsapp_messaging' ---"))

        # The 'default' database alias must be your public database
        # from which you can retrieve the list of all tenants.
        self.stdout.write("Fetching tenants from the 'default' (public) database...")
        try:
            tenants = Tenant.objects.all()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to fetch tenants: {e}"))
            self.stdout.write(self.style.WARNING("Please ensure your 'tenants' app is configured and migrated correctly."))
            return

        if not tenants:
            self.stdout.write(self.style.WARNING("No tenants found in the database. Exiting."))
            return

        for tenant in tenants:
            tenant_db_alias = f"crm_db_{tenant.tenant_id}"
            self.stdout.write(self.style.SUCCESS(f"\nMigrating database '{tenant_db_alias}' for tenant '{tenant.tenant_id}'..."))
            
            # Use the --database option to specify the tenant's database.
            # You must have a database entry in your settings.py for each tenant.
            # For example:
            # DATABASES = {
            #     'default': {...},
            #     'crm_db_pukul_com': {...},
            #     'crm_db_example_com': {...}
            # }
            try:
                call_command('migrate', 'whatsapp_messaging', database=tenant_db_alias, verbosity=0)
                self.stdout.write(self.style.SUCCESS(f"Migration for '{tenant.tenant_id}' successful."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error migrating '{tenant_db_alias}': {e}"))
                self.stdout.write(self.style.WARNING(f"Skipping tenant '{tenant.tenant_id}'..."))
        
        self.stdout.write(self.style.SUCCESS("\n--- All tenant migrations completed ---"))
