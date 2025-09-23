# marketing_campaigns/management/commands/setup_marketing_campaigns_tenant.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from tenants.context import set_current_db, clear_current_db
from tenants.models import Tenant
from marketing_campaigns.models import (
    TenantCampaignSettings, CampaignCategory, MessageTemplate, TargetingReport
)

class Command(BaseCommand):
    help = 'Setup marketing campaigns for a specific tenant'

    def add_arguments(self, parser):
        parser.add_argument('tenant_id', type=str, help='Tenant ID to setup campaigns for')

    def handle(self, *args, **options):
        tenant_id = options['tenant_id']
        
        try:
            # Get tenant and set database context
            tenant = Tenant.objects.using('default').get(tenant_id=tenant_id)
            set_current_db(tenant.db_alias)
            
            self.stdout.write(f"Setting up marketing campaigns for tenant: {tenant.name} ({tenant_id})")
            self.stdout.write(f"Using database: {tenant.db_alias}")
            
            # 1. Create tenant settings
            self.stdout.write("\n1. Creating tenant settings...")
            settings, created = TenantCampaignSettings.objects.get_or_create(
                id=1,
                defaults={
                    'primary_country_code': 'ID',
                    'supported_countries': ['ID', 'MY', 'TH', 'SG', 'PH'],
                    'custom_variables': {
                        'bonus': {'type': 'currency', 'description': 'Bonus amount'},
                        'coupon_code': {'type': 'text', 'description': 'Promotional code'}
                    }
                }
            )
            action = "✅ Created" if created else "✅ Already exists"
            self.stdout.write(f"{action}: Tenant settings (Country: {settings.primary_country_code})")

            # 2. Create default categories
            self.stdout.write("\n2. Creating default categories...")
            categories_data = [
                {'name': 'Welcome Messages', 'description': 'New member welcome campaigns', 'color': '#28a745', 'icon': 'welcome'},
                {'name': 'Deposit Promotions', 'description': 'Deposit bonus and promotions', 'color': '#ffc107', 'icon': 'coins'},
                {'name': 'VIP & Loyalty', 'description': 'VIP member exclusive offers', 'color': '#6f42c1', 'icon': 'crown'},
                {'name': 'Win-Back', 'description': 'Re-engage inactive members', 'color': '#dc3545', 'icon': 'arrow-back'},
            ]
            
            for cat_data in categories_data:
                category, created = CampaignCategory.objects.get_or_create(
                    name=cat_data['name'],
                    defaults={
                        'description': cat_data['description'],
                        'color': cat_data['color'],
                        'icon': cat_data['icon'],
                        'is_system_default': True,
                        'created_by': 'system'
                    }
                )
                action = "✅ Created" if created else "✅ Already exists"
                self.stdout.write(f"{action}: {category.name}")

            # 3. Create default template
            self.stdout.write("\n3. Creating default template...")
            welcome_category = CampaignCategory.objects.get(name='Welcome Messages')
            template, created = MessageTemplate.objects.get_or_create(
                name='Selamat Datang - Member Baru',
                defaults={
                    'description': 'Template welcome untuk member baru dengan bonus',
                    'category': welcome_category,
                    'content': 'Halo {{name}}! 🎉 Selamat datang di platform kami. Bonus {{bonus}} sudah menanti Anda!',
                    'variation_a': 'Hi {{name}}! 🌟 Terima kasih telah bergabung. Claim bonus {{bonus}} Anda sekarang!',
                    'variation_b': 'Welcome {{name}}! 🎊 Kami senang Anda bergabung. Bonus {{bonus}} siap untuk Anda!',
                    'use_variations': True,
                    'is_system_template': True,
                    'created_by': 'system'
                }
            )
            action = "✅ Created" if created else "✅ Already exists"
            self.stdout.write(f"{action}: {template.name}")

            # 4. Create targeting reports
            self.stdout.write("\n4. Creating targeting reports...")
            reports_data = [
                {
                    'name': 'New Members (Last 7 Days)',
                    'description': 'Members who joined within the last 7 days',
                    'query_criteria': {
                        'days_since_join': {'operator': '<=', 'value': 7}
                    }
                },
                {
                    'name': 'VIP Inactive Members',
                    'description': 'High-value members with no activity for 30+ days',
                    'query_criteria': {
                        'total_deposits': {'operator': '>=', 'value': 1000000},
                        'days_since_last_deposit': {'operator': '>=', 'value': 30}
                    }
                },
                {
                    'name': 'High Depositors',
                    'description': 'Members with deposits over 5M in last 30 days',
                    'query_criteria': {
                        'deposit_last_30_days': {'operator': '>=', 'value': 5000000}
                    }
                }
            ]
            
            for report_data in reports_data:
                report, created = TargetingReport.objects.get_or_create(
                    name=report_data['name'],
                    defaults={
                        'description': report_data['description'],
                        'query_criteria': report_data['query_criteria']
                    }
                )
                action = "✅ Created" if created else "✅ Already exists"
                self.stdout.write(f"{action}: {report.name}")

            # Summary
            categories_count = CampaignCategory.objects.count()
            templates_count = MessageTemplate.objects.count()
            reports_count = TargetingReport.objects.count()
            
            self.stdout.write(f"\n📊 SUMMARY for {tenant.name}:")
            self.stdout.write(f"Categories: {categories_count}")
            self.stdout.write(f"Templates: {templates_count}")
            self.stdout.write(f"Targeting Reports: {reports_count}")
            self.stdout.write(f"\n🎉 Marketing campaigns system ready for {tenant.name}!")
            
        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Tenant '{tenant_id}' not found"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
        finally:
            clear_current_db()