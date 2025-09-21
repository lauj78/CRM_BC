import os
from django.core.management.base import BaseCommand
from django.core.management import call_command
from tenants.models import Tenant # Your existing Tenant model

class Command(BaseCommand):
    help = 'Runs migrations for the whatsapp_messaging app on all tenant databases.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- Starting multi-tenant migration for 'whatsapp_messaging' ---"))

        # Since you only have two specific databases, we'll iterate directly over them.
        # This bypasses any issues with the dynamic name generation.
        tenant_db_aliases = ['crm_db_pukul_com', 'crm_db_test_com']

        for tenant_db_alias in tenant_db_aliases:
            self.stdout.write(self.style.SUCCESS(f"\nMigrating database '{tenant_db_alias}'..."))
            
            # Use the --database option to specify the tenant's database.
            try:
                # Note: The `management` and `commands` folders must both have a __init__.py file
                # to be recognized as a Python package by Django.
                call_command('migrate', 'whatsapp_messaging', database=tenant_db_alias, verbosity=0)
                self.stdout.write(self.style.SUCCESS(f"Migration for '{tenant_db_alias}' successful."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error migrating '{tenant_db_alias}': {e}"))
                self.stdout.write(self.style.WARNING(f"Skipping database '{tenant_db_alias}'..."))
        
        self.stdout.write(self.style.SUCCESS("\n--- All tenant migrations completed ---"))
