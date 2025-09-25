# marketing_campaigns/apps.py

from django.apps import AppConfig

class MarketingCampaignsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'marketing_campaigns'
    
    def ready(self):
        # Import tasks to ensure they're registered with Celery
        try:
            from . import tasks
        except ImportError:
            pass