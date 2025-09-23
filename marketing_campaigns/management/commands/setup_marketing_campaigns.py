# marketing_campaigns/management/commands/setup_marketing_campaigns.py
from django.core.management.base import BaseCommand
from marketing_campaigns.models import (
    TenantCampaignSettings, CampaignCategory, MessageTemplate, TargetingReport
)

class Command(BaseCommand):
    help = 'Setup initial marketing campaign data'
    
    def handle(self, *args, **options):
        self.stdout.write('Setting up marketing campaigns system...')
        
        # 1. Create tenant settings
        self.stdout.write('\n1. Creating tenant settings...')
        settings = TenantCampaignSettings.get_instance()
        self.stdout.write(f'✅ Tenant settings ready (Country: {settings.primary_country_code})')
        
        # 2. Create default categories
        self.stdout.write('\n2. Creating default categories...')
        default_categories = [
            {
                'name': 'Welcome Messages',
                'description': 'New member welcome and onboarding',
                'color': '#28a745',
                'icon': 'user-plus',
                'is_system_default': True,
                'created_by': 'system'
            },
            {
                'name': 'Deposit Promotions', 
                'description': 'Deposit bonuses and offers',
                'color': '#17a2b8',
                'icon': 'credit-card',
                'is_system_default': True,
                'created_by': 'system'
            },
            {
                'name': 'VIP & Loyalty',
                'description': 'VIP member exclusive offers',
                'color': '#ffc107',
                'icon': 'crown',
                'is_system_default': True,
                'created_by': 'system'
            },
            {
                'name': 'Win-Back',
                'description': 'Re-engage inactive players',
                'color': '#dc3545',
                'icon': 'heart',
                'is_system_default': True,
                'created_by': 'system'
            }
        ]
        
        categories_created = 0
        for cat_data in default_categories:
            category, created = CampaignCategory.objects.get_or_create(
                name=cat_data['name'],
                defaults=cat_data
            )
            if created:
                categories_created += 1
                self.stdout.write(f'✅ Created: {category.name}')
        
        if categories_created == 0:
            self.stdout.write('ℹ️  All default categories already exist')
        
        # 3. Create Indonesian welcome template
        self.stdout.write('\n3. Creating Indonesian welcome template...')
        welcome_cat = CampaignCategory.objects.get(name='Welcome Messages')
        
        template_data = {
            'name': 'Selamat Datang - Member Baru',
            'description': 'Template selamat datang untuk member baru casino',
            'category': welcome_cat,
            'content': """🎰 Selamat datang di Casino kami, {{name}}! 

Akun Anda sudah aktif dan siap untuk bermain!

🎁 BONUS SELAMAT DATANG:
• Bonus Deposit Pertama 100% hingga Rp 500,000
• 50 Putaran Gratis di slot populer
• Customer service 24/7

Siap merasakan sensasi kemenangan? Deposit pertama Anda menanti!

💎 Ada pertanyaan? Balas pesan ini kapan saja.""",
            
            'variation_a': """🌟 Halo {{name}}, selamat bergabung! 

Akun Anda sudah siap untuk petualangan menang besar!

🎊 PAKET MEMBER BARU:
• Gandakan deposit pertama (maks Rp 500,000)
• 50 spin bonus included
• Tim support siaga 24 jam

Mari mulai sesi kemenangan pertama Anda!

Butuh bantuan? Kami siap membantu! 🎮""",
            
            'use_variations': True,
            'is_system_template': True,
            'created_by': 'system',
            'is_active': True
        }
        
        template, created = MessageTemplate.objects.get_or_create(
            name=template_data['name'],
            defaults=template_data
        )
        
        if created:
            self.stdout.write(f'✅ Created template: {template.name}')
        else:
            self.stdout.write(f'ℹ️  Template already exists: {template.name}')
        
        # 4. Create default targeting reports
        self.stdout.write('\n4. Creating targeting reports...')
        default_reports = [
            {
                'name': 'New Members (Last 7 Days)',
                'description': 'Members who joined in the last 7 days',
                'query_criteria': {
                    'days_since_join': {'operator': '<=', 'value': 7}
                }
            },
            {
                'name': 'VIP Inactive Members', 
                'description': 'VIP members inactive for 30+ days',
                'query_criteria': {
                    'vip_level': {'operator': 'in', 'value': ['Gold', 'Platinum', 'Diamond']},
                    'days_since_last_deposit': {'operator': '>=', 'value': 30}
                }
            },
            {
                'name': 'High Depositors',
                'description': 'Members with total deposits >= 10,000',
                'query_criteria': {
                    'total_deposits': {'operator': '>=', 'value': 10000}
                }
            }
        ]
        
        reports_created = 0
        for report_data in default_reports:
            report, created = TargetingReport.objects.get_or_create(
                name=report_data['name'],
                defaults=report_data
            )
            if created:
                reports_created += 1
                self.stdout.write(f'✅ Created: {report.name}')
        
        if reports_created == 0:
            self.stdout.write('ℹ️  All targeting reports already exist')
        
        # 5. Summary
        total_categories = CampaignCategory.objects.count()
        total_templates = MessageTemplate.objects.count()
        total_reports = TargetingReport.objects.count()
        
        self.stdout.write('\n📊 SUMMARY:')
        self.stdout.write(f'Categories: {total_categories}')
        self.stdout.write(f'Templates: {total_templates}')
        self.stdout.write(f'Targeting Reports: {total_reports}')
        
        self.stdout.write(
            self.style.SUCCESS('\n🎉 Marketing campaigns system is ready!')
        )
