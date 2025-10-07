# marketing_campaigns/services/anti_ban_service.py

import logging
import random
from datetime import timedelta
from django.utils import timezone
from django.db import transaction

from whatsapp_messaging.models import WhatsAppInstance
from marketing_campaigns.models_usage import WhatsAppInstanceUsage
from marketing_campaigns.models import TenantCampaignSettings

logger = logging.getLogger(__name__)


class AntiBanService:
    """
    Centralized service for anti-ban strategy and instance management
    Handles instance selection, rate limiting, and usage tracking
    """
    
    def __init__(self, tenant_id=None, database_alias=None):
        """
        Initialize service with tenant context
        
        Args:
            tenant_id: Tenant ID for filtering WhatsApp instances
            database_alias: Which database to query (e.g., 'crm_db_pukul_com')
        """
        self.tenant_id = tenant_id
        
        # Auto-detect database if not provided
        if database_alias is None:
            database_alias = self._get_database_for_tenant(tenant_id)
        
        self.database_alias = database_alias
        
        # Query settings from correct database
        self.settings = TenantCampaignSettings.objects.using(self.database_alias).get_or_create(
            tenant_id=tenant_id,
            defaults={
                'instance_selection_strategy': 'round_robin',
                'max_messages_per_instance_hour': 10,
                'max_messages_per_instance_day': 200,
                'min_delay_seconds': 60,
                'max_delay_seconds': 180,
                'use_random_delays': True,
                'rotate_after_messages': 50,
                'instance_cooldown_minutes': 15,
                'auto_disable_failed_instances': True,
                'failure_threshold': 5,
            }
        )[0]
        
        logger.debug(f"AntiBanService initialized for tenant {tenant_id}, database {database_alias}")
    
    def _get_database_for_tenant(self, tenant_id):
        """Map tenant_id to database alias"""
        if tenant_id == 2:
            return 'crm_db_pukul_com'
        elif tenant_id == 3:
            return 'crm_db_test_com'
        else:
            return 'default'
    
    def get_available_instances(self):
        """
        Get all active WhatsApp instances for this tenant
        
        Returns:
            QuerySet of WhatsAppInstance objects
        """
        filters = {
            'is_active': True,
            'status': 'connected'
        }
        
        if self.tenant_id:
            filters['tenant_id'] = self.tenant_id
        
        # FIXED: Use correct database
        instances = WhatsAppInstance.objects.using(self.database_alias).filter(**filters)
        
        logger.debug(f"Found {instances.count()} available instances for tenant {self.tenant_id} in {self.database_alias}")
        return instances
    
    def get_or_create_usage(self, instance_name):
        """
        Get or create usage tracking record for an instance
        
        Args:
            instance_name: WhatsApp instance name
            
        Returns:
            WhatsAppInstanceUsage object
        """
        # FIXED: Use correct database
        usage, created = WhatsAppInstanceUsage.objects.using(self.database_alias).get_or_create(
            instance_name=instance_name,
            defaults={
                'messages_sent_today': 0,
                'messages_sent_this_hour': 0,
                'consecutive_failures': 0,
            }
        )
        
        if created:
            logger.info(f"Created new usage tracking for instance: {instance_name}")
        
        # Always check and reset counters on retrieval
        usage.check_and_reset_counters()
        
        return usage
    
    def select_instance_for_campaign(self, campaign):
        """
        Select the best WhatsApp instance for sending based on tenant strategy
        
        Args:
            campaign: Campaign object
            
        Returns:
            WhatsAppInstance object or None if no instance available
        """
        strategy = self.settings.instance_selection_strategy
        
        logger.info(f"Selecting instance using strategy: {strategy}")
        
        if strategy == 'round_robin':
            return self._select_round_robin()
        elif strategy == 'random':
            return self._select_random()
        elif strategy == 'least_used':
            return self._select_least_used()
        else:
            logger.warning(f"Unknown strategy '{strategy}', falling back to round_robin")
            return self._select_round_robin()
    
    def _select_round_robin(self):
        """
        Select instance using round-robin rotation
        Ensures even distribution across all instances
        
        Returns:
            WhatsAppInstance object or None
        """
        instances = self.get_available_instances()
        
        if not instances.exists():
            logger.error("No available WhatsApp instances found")
            return None
        
        # Get all instances with their usage data
        instance_usages = []
        for instance in instances:
            usage = self.get_or_create_usage(instance.instance_name)
            
            # Check if this instance can send
            can_send, reason = self.can_send_now(instance)
            
            instance_usages.append({
                'instance': instance,
                'usage': usage,
                'can_send': can_send,
                'reason': reason,
                'position': usage.last_used_position
            })
        
        # Filter to only instances that can send
        available = [iu for iu in instance_usages if iu['can_send']]
        
        if not available:
            logger.warning("No instances currently available to send (all in cooldown or at limits)")
            for iu in instance_usages:
                if not iu['can_send']:
                    logger.debug(f"  {iu['instance'].instance_name}: {iu['reason']}")
            return None
        
        # Sort by position to find next in rotation
        available.sort(key=lambda x: x['position'])
        
        # Select the one with lowest position
        selected = available[0]
        selected_instance = selected['instance']
        selected_usage = selected['usage']
        
        # Update position AFTER selection
        selected_usage.last_used_position += 1
        selected_usage.save(using=self.database_alias, update_fields=['last_used_position'])
        
        # Only reset when ALL instances have been used at least once
        all_positions = [iu['usage'].last_used_position for iu in instance_usages]
        min_position = min(all_positions)
        
        # If the minimum position is > 0, it means all instances were used - start new round
        if min_position > 0:
            logger.info("Round-robin cycle completed, resetting all positions")
            for iu in instance_usages:
                iu['usage'].last_used_position = 0
                iu['usage'].save(using=self.database_alias, update_fields=['last_used_position'])
        
        logger.info(f"Round-robin selected: {selected_instance.instance_name} "
                    f"(today: {selected_usage.messages_sent_today}, "
                    f"hour: {selected_usage.messages_sent_this_hour}, "
                    f"position: {selected_usage.last_used_position})")
        
        return selected_instance
    
    def _select_random(self):
        """
        Select a random available instance
        """
        instances = self.get_available_instances()
        
        if not instances.exists():
            logger.error("No available WhatsApp instances found")
            return None
        
        # Get all instances that can send
        available = []
        for instance in instances:
            can_send, reason = self.can_send_now(instance)
            if can_send:
                available.append(instance)
            else:
                logger.debug(f"{instance.instance_name}: {reason}")
        
        if not available:
            logger.warning("No instances currently available to send")
            return None
        
        # Select random
        selected = random.choice(available)
        logger.info(f"Random selected: {selected.instance_name}")
        return selected
    
    def _select_least_used(self):
        """
        Select the least used instance today
        """
        instances = self.get_available_instances()
        
        if not instances.exists():
            logger.error("No available WhatsApp instances found")
            return None
        
        # Get all instances with usage
        instance_usages = []
        for instance in instances:
            usage = self.get_or_create_usage(instance.instance_name)
            can_send, reason = self.can_send_now(instance)
            
            if can_send:
                instance_usages.append({
                    'instance': instance,
                    'usage': usage,
                    'messages_today': usage.messages_sent_today
                })
        
        if not instance_usages:
            logger.warning("No instances currently available to send")
            return None
        
        # Sort by messages sent today (ascending)
        instance_usages.sort(key=lambda x: x['messages_today'])
        
        selected = instance_usages[0]['instance']
        logger.info(f"Least-used selected: {selected.instance_name} "
                    f"(today: {instance_usages[0]['messages_today']})")
        return selected
    
    def can_send_now(self, instance):
        """
        Check if instance can send a message now based on rate limits
        
        Args:
            instance: WhatsAppInstance object
            
        Returns:
            tuple: (can_send: bool, reason: str)
        """
        usage = self.get_or_create_usage(instance.instance_name)
        
        # Check if in cooldown
        if not usage.is_available():
            return False, f"Instance in cooldown until {usage.cooldown_until}"
        
        # Check hourly limit
        if usage.messages_sent_this_hour >= self.settings.max_messages_per_instance_hour:
            return False, f"Hourly limit reached ({usage.messages_sent_this_hour}/{self.settings.max_messages_per_instance_hour})"
        
        # Check daily limit
        if usage.messages_sent_today >= self.settings.max_messages_per_instance_day:
            return False, f"Daily limit reached ({usage.messages_sent_today}/{self.settings.max_messages_per_instance_day})"
        
        # Check consecutive failures
        if usage.consecutive_failures >= self.settings.failure_threshold:
            return False, f"Too many consecutive failures ({usage.consecutive_failures})"
        
        return True, "OK"
    
    def record_message_sent(self, instance, success=True, error_message=None):
        """
        Record that a message was sent from this instance
        
        Args:
            instance: WhatsAppInstance object
            success: Whether message was sent successfully
            error_message: Error message if failed
        """
        usage = self.get_or_create_usage(instance.instance_name)
        usage.record_message_sent(success=success)
        
        # Handle failures
        if not success:
            logger.warning(f"Message failed on {instance.instance_name}: {error_message}")
            
            # Auto-disable if threshold reached
            if (self.settings.auto_disable_failed_instances and 
                usage.consecutive_failures >= self.settings.failure_threshold):
                
                logger.error(f"Disabling instance {instance.instance_name} due to {usage.consecutive_failures} consecutive failures")
                instance.is_active = False
                instance.save(using=self.database_alias, update_fields=['is_active'])
                
                # Put in long cooldown
                usage.enter_cooldown(minutes=60)
        
        # Check if rotation needed
        if usage.messages_sent_today % self.settings.rotate_after_messages == 0:
            logger.info(f"Instance {instance.instance_name} reached rotation threshold, entering cooldown")
            usage.enter_cooldown(minutes=self.settings.instance_cooldown_minutes)
    
    def calculate_next_delay(self, campaign=None):
        """
        Calculate delay before next message (in seconds)
        
        Args:
            campaign: Campaign object (optional, for campaign-specific overrides)
            
        Returns:
            int: Seconds to wait before next message
        """
        min_delay = self.settings.min_delay_seconds
        max_delay = self.settings.max_delay_seconds
        
        if self.settings.use_random_delays:
            delay = random.randint(min_delay, max_delay)
            logger.debug(f"Calculated random delay: {delay} seconds")
        else:
            delay = min_delay
            logger.debug(f"Using minimum delay: {delay} seconds")
        
        return delay
    
    def get_instance_health_status(self, instance):
        """
        Get health metrics for an instance
        
        Args:
            instance: WhatsAppInstance object
            
        Returns:
            dict: Health metrics
        """
        usage = self.get_or_create_usage(instance.instance_name)
        
        return {
            'instance_name': instance.instance_name,
            'is_available': usage.is_available(),
            'messages_today': usage.messages_sent_today,
            'messages_this_hour': usage.messages_sent_this_hour,
            'success_rate': usage.success_rate,
            'consecutive_failures': usage.consecutive_failures,
            'in_cooldown': usage.is_in_cooldown,
            'cooldown_until': usage.cooldown_until,
            'last_used': usage.last_message_sent_at,
        }
    
    def get_all_instances_health(self):
        """
        Get health status for all instances
        
        Returns:
            list: List of health status dicts
        """
        instances = self.get_available_instances()
        return [self.get_instance_health_status(inst) for inst in instances]