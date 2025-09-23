# marketing_campaigns/apps.py
from django.apps import AppConfig

class MarketingCampaignsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'marketing_campaigns'
    verbose_name = 'Marketing Campaigns'