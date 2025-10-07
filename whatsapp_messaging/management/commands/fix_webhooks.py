from django.core.management.base import BaseCommand
from django.conf import settings
from tenants.models import Tenant
from whatsapp_messaging.models import WhatsAppInstance
from whatsapp_messaging.services.evolution_api import EvolutionAPIService
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Fix webhook URLs for all WhatsApp instances (one-time fix for existing instances)'
    
    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show changes without applying')
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        service = EvolutionAPIService()
        
        # Determine base URL
        if hasattr(settings, 'SITE_URL') and settings.SITE_URL:
            base_url = settings.SITE_URL
        else:
            base_url = 'http://172.19.0.1:8000'  # Docker default
        
        self.stdout.write(self.style.SUCCESS(f"Using base URL: {base_url}\n"))
        
        total_fixed = 0
        total_failed = 0
        total_skipped = 0
        
        for tenant in Tenant.objects.all():
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write(f"Tenant: {tenant.tenant_id}")
            self.stdout.write('='*60)
            
            db_alias = f"crm_db_{tenant.tenant_id.replace('.', '_')}"
            
            try:
                instances = WhatsAppInstance.objects.using(db_alias).filter(
                    tenant_id=tenant.id,
                    is_active=True
                )
                
                if not instances.exists():
                    self.stdout.write(self.style.WARNING('  No active instances'))
                    total_skipped += 1
                    continue
                
                for instance in instances:
                    webhook_url = f"{base_url}/tenant/{tenant.tenant_id}/whatsapp/webhooks/evolution/"
                    
                    self.stdout.write(f"\n{instance.instance_name}")
                    self.stdout.write(f"  Webhook: {webhook_url}")
                    
                    if not dry_run:
                        # Try nested format first
                        data = {
                            'webhook': {
                                'url': webhook_url,
                                'enabled': True,
                                'events': ['MESSAGES_UPSERT', 'MESSAGES_UPDATE', 'CONNECTION_UPDATE'],
                                'webhookByEvents': False
                            }
                        }
                        
                        result = service._make_request('POST', f'webhook/set/{instance.instance_name}', data)
                        
                        # If nested fails, try flat format with PUT
                        if not result['success'] and 'requires property' in result.get('error', ''):
                            data = {
                                'url': webhook_url,
                                'enabled': True,
                                'events': ['MESSAGES_UPSERT', 'MESSAGES_UPDATE', 'CONNECTION_UPDATE'],
                                'webhookByEvents': False
                            }
                            result = service._make_request('PUT', f'webhook/set/{instance.instance_name}', data)
                        
                        if result['success']:
                            self.stdout.write(self.style.SUCCESS('  ✓ Updated'))
                            total_fixed += 1
                        else:
                            self.stdout.write(self.style.ERROR(f'  ✗ Failed: {result.get("error")}'))
                            total_failed += 1
                                                    
            except Exception as e:
                # Gracefully skip tenants without WhatsApp tables
                error_msg = str(e)
                if 'does not exist' in error_msg or 'no such table' in error_msg:
                    self.stdout.write(self.style.WARNING('  ⚠ WhatsApp not set up yet - skipping'))
                    total_skipped += 1
                else:
                    self.stdout.write(self.style.ERROR(f'  ✗ Error: {error_msg}'))
                    total_failed += 1
        
        self.stdout.write("\n" + "="*60)
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes made'))
            self.stdout.write(self.style.WARNING('Run without --dry-run to apply changes'))
        else:
            self.stdout.write(self.style.SUCCESS(f'✓ Fixed: {total_fixed} instances'))
            if total_skipped > 0:
                self.stdout.write(self.style.WARNING(f'⚠ Skipped: {total_skipped} tenants (no WhatsApp setup)'))
            if total_failed > 0:
                self.stdout.write(self.style.ERROR(f'✗ Failed: {total_failed} instances'))
        self.stdout.write("="*60)