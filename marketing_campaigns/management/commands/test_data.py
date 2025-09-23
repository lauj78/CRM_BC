# marketing_campaigns/management/commands/test_data.py
from django.core.management.base import BaseCommand
from marketing_campaigns.models import *

class Command(BaseCommand):
    help = 'Test and inspect marketing campaign data'
    
    def add_arguments(self, parser):
        parser.add_argument('--model', type=str, help='Test specific model')
    
    def handle(self, *args, **options):
        if options.get('model') == 'settings':
            self.test_settings()
        elif options.get('model') == 'categories':
            self.test_categories()
        elif options.get('model') == 'templates':
            self.test_templates()
        else:
            self.test_all()
    
    def test_settings(self):
        self.stdout.write('Testing TenantCampaignSettings...')
        settings = TenantCampaignSettings.get_instance()
        self.stdout.write(f'Primary Country: {settings.primary_country_code}')
        self.stdout.write(f'Supported Countries: {settings.supported_countries}')
        self.stdout.write(f'Default Rate Limit: {settings.default_rate_limit_per_hour}/hour')
        self.stdout.write(f'Custom Variables: {list(settings.custom_variables.keys())}')
    
    def test_categories(self):
        self.stdout.write('Testing CampaignCategory...')
        categories = CampaignCategory.objects.all()
        for cat in categories:
            self.stdout.write(f'- {cat.name} (System: {cat.is_system_default})')
    
    def test_templates(self):
        self.stdout.write('Testing MessageTemplate...')
        templates = MessageTemplate.objects.all()
        for template in templates:
            self.stdout.write(f'- {template.name}')
            self.stdout.write(f'  Variables: {template.variables_used}')
            self.stdout.write(f'  Has variations: {template.use_variations}')
    
    def test_all(self):
        self.stdout.write('Testing all models...\n')
        self.test_settings()
        self.stdout.write()
        self.test_categories()
        self.stdout.write()
        self.test_templates()