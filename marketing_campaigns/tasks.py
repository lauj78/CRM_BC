# marketing_campaigns/tasks.py - CLEAN TENANT ARCHITECTURE

import logging
import time
import random
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.conf import settings

from .models import Campaign, CampaignTarget, MessageTemplate
from whatsapp_messaging.models import WhatsAppInstance
from whatsapp_messaging.services.evolution_api import EvolutionAPIService
from tenants.context import set_current_db

logger = logging.getLogger('marketing_campaigns')

def _set_tenant_context_for_campaign(campaign_id):
    """
    Auto-detect tenant database for campaign and set context
    This maintains clean architecture while solving the Celery context issue
    """
    from django.db import connections
    
    # Get all tenant databases from settings
    tenant_databases = [db for db in settings.DATABASES.keys() if db != 'default']
    
    for db_name in tenant_databases:
        try:
            # Try to find campaign in this database
            campaign = Campaign.objects.using(db_name).get(pk=campaign_id)
            # Found it! Set context and log
            set_current_db(db_name)
            logger.info(f"[CELERY] Auto-detected tenant context: {db_name} for campaign {campaign_id}")
            return db_name
        except Campaign.DoesNotExist:
            continue
    
    # If not found in any tenant database, log error but don't crash
    logger.warning(f"[CELERY] Campaign {campaign_id} not found in any tenant database")
    return None

def _set_tenant_context_for_target(target_id):
    """
    Auto-detect tenant database for campaign target and set context
    """
    from django.db import connections
    
    # Get all tenant databases from settings
    tenant_databases = [db for db in settings.DATABASES.keys() if db != 'default']
    
    for db_name in tenant_databases:
        try:
            # Try to find target in this database
            target = CampaignTarget.objects.using(db_name).get(pk=target_id)
            # Found it! Set context and log
            set_current_db(db_name)
            logger.info(f"[CELERY] Auto-detected tenant context: {db_name} for target {target_id}")
            return db_name
        except CampaignTarget.DoesNotExist:
            continue
    
    # If not found in any tenant database, log error but don't crash
    logger.warning(f"[CELERY] Target {target_id} not found in any tenant database")
    return None

@shared_task(bind=True, max_retries=3)
def process_campaign_messages(self, campaign_id):
    """
    Main task to process campaign messages - SIMPLIFIED for clean tenant architecture
    """
    logger.info(f"[CELERY] Starting message processing for campaign {campaign_id}")
    
    try:
        # Auto-detect and set tenant context for clean architecture
        _set_tenant_context_for_campaign(campaign_id)
        
        # Simple lookup - router now has correct context
        campaign = Campaign.objects.get(pk=campaign_id)
        
        if campaign.status != 'running':
            logger.warning(f"[CELERY] Campaign {campaign_id} is not running (status: {campaign.status})")
            return f"Campaign not running: {campaign.status}"
        
        # Get pending targets - simple query, router handles database
        max_messages_this_hour = campaign.rate_limit_per_hour
        targets = campaign.targets.filter(status='queued')[:max_messages_this_hour]
        
        logger.info(f"[CELERY] Processing {targets.count()} targets for campaign {campaign_id}")
        
        if not targets.exists():
            logger.info(f"[CELERY] No pending targets for campaign {campaign_id}")
            # Check if campaign is complete - simple query
            if campaign.targets.filter(status__in=['queued', 'scheduled']).count() == 0:
                campaign.status = 'completed'
                campaign.save()
                logger.info(f"[CELERY] Campaign {campaign_id} marked as completed")
            return "No pending targets"
        
        # Process each target with delays
        processed_count = 0
        for target in targets:
            try:
                # Send message - no complex parameters needed
                result = send_single_message.delay(target.pk)
                processed_count += 1
                
                # Anti-ban delay between messages
                delay_minutes = random.randint(
                    campaign.min_delay_minutes, 
                    campaign.max_delay_minutes
                )
                logger.info(f"[CELERY] Processed target {target.pk}, next delay: {delay_minutes} minutes")
                
                # Schedule next message with delay
                if processed_count < targets.count():
                    next_target = list(targets)[processed_count]
                    send_single_message.apply_async(
                        args=[next_target.pk],
                        countdown=delay_minutes * 60
                    )
                
            except Exception as e:
                logger.error(f"[CELERY] Error processing target {target.pk}: {str(e)}")
                continue
        
        # Schedule next batch if more targets exist - simple query
        remaining_targets = campaign.targets.filter(status='queued').count()
        if remaining_targets > 0 and campaign.status == 'running':
            # Schedule next batch in 1 hour (rate limiting)
            process_campaign_messages.apply_async(
                args=[campaign_id],
                countdown=3600  # 1 hour
            )
            logger.info(f"[CELERY] Scheduled next batch for campaign {campaign_id} in 1 hour")
        
        return f"Processed {processed_count} messages"
        
    except Campaign.DoesNotExist:
        logger.error(f"[CELERY] Campaign {campaign_id} not found")
        return f"Campaign {campaign_id} not found"
    except Exception as e:
        logger.error(f"[CELERY] Unexpected error processing campaign {campaign_id}: {str(e)}")
        raise self.retry(countdown=300, exc=e)  # Retry in 5 minutes

@shared_task(bind=True, max_retries=3)
def send_single_message(self, target_id):
    """
    Send a single message to a target - SIMPLIFIED for clean tenant architecture
    """
    logger.info(f"[CELERY] Sending message to target {target_id}")
    
    try:
        # Auto-detect and set tenant context for clean architecture
        _set_tenant_context_for_target(target_id)
        
        with transaction.atomic():
            # Simple lookups - router now has correct context (remove select_for_update)
            target = CampaignTarget.objects.get(pk=target_id)
            campaign = Campaign.objects.get(pk=target.campaign_id)
            
            if target.status != 'queued':
                logger.warning(f"[CELERY] Target {target_id} status is {target.status}, skipping")
                return f"Target not queued: {target.status}"
            
            # Update target status
            target.status = 'sending'
            target.save()
            
            # Get campaign template - simple relationship lookup
            campaign_message = campaign.campaign_messages.first()
            if not campaign_message:
                raise Exception("No template found for campaign")
            
            # Get template - simple lookup, router handles database
            template = MessageTemplate.objects.get(pk=campaign_message.template_id)
            rendered_message = template.render_message(target.member_data)
            
            # Get WhatsApp instance - simple lookup, router handles database
            whatsapp_instance = WhatsAppInstance.objects.filter(
                is_active=True,
                status='connected'
            ).first()
            
            if not whatsapp_instance:
                raise Exception("No active WhatsApp instance found")
            
            # Send message via Evolution API
            service = EvolutionAPIService()
            result = service.send_text_message(
                instance_name=whatsapp_instance.instance_name,
                phone=target.phone_number,
                message=rendered_message
            )
            
            # Update target based on result
            if result['success']:
                target.status = 'sent'
                target.sent_at = timezone.now()
                target.final_message = rendered_message
                target.evolution_api_response = result
                
                # Update campaign stats
                campaign.total_sent += 1
                campaign.save()
                
                logger.info(f"[CELERY] Successfully sent message to {target.phone_number}")
                
            else:
                target.status = 'failed'
                target.error_message = result.get('error', 'Unknown error')
                target.retry_count += 1
                target.evolution_api_response = result
                
                # Update campaign stats
                campaign.total_failed += 1
                campaign.save()
                
                logger.error(f"[CELERY] Failed to send message to {target.phone_number}: {target.error_message}")
                
                # Retry if under limit
                if target.retry_count < campaign.max_retry_per_number:
                    target.status = 'queued'
                    logger.info(f"[CELERY] Queued target {target_id} for retry ({target.retry_count}/{campaign.max_retry_per_number})")
            
            target.save()
            
        return f"Message sent to {target.phone_number}: {result['success']}"
        
    except CampaignTarget.DoesNotExist:
        logger.error(f"[CELERY] Target {target_id} not found")
        return f"Target {target_id} not found"
    except Exception as e:
        logger.error(f"[CELERY] Error sending message to target {target_id}: {str(e)}")
        
        # Update target status on error
        try:
            target = CampaignTarget.objects.get(pk=target_id)
            target.status = 'failed'
            target.error_message = str(e)
            target.retry_count += 1
            target.save()
        except:
            pass
            
        raise self.retry(countdown=60, exc=e)  # Retry in 1 minute

@shared_task
def cleanup_old_campaign_data():
    """
    Periodic task to clean up old campaign data - SIMPLIFIED
    Cleans up campaigns across all tenant databases
    """
    logger.info("[CELERY] Starting cleanup of old campaign data")
    
    from django.conf import settings
    
    # Get all tenant databases
    tenant_databases = [db for db in settings.DATABASES.keys() if db != 'default']
    
    total_cleaned = 0
    for db_name in tenant_databases:
        try:
            # Set context for this tenant database
            set_current_db(db_name)
            
            # Simple query - router now has correct context
            old_campaigns = Campaign.objects.filter(
                status='running',
                created_at__lt=timezone.now() - timedelta(days=7)
            )
            
            for campaign in old_campaigns:
                pending_targets = campaign.targets.filter(status__in=['queued', 'scheduled']).count()
                if pending_targets == 0:
                    campaign.status = 'completed'
                    campaign.save()
                    total_cleaned += 1
                    logger.info(f"[CELERY] Marked old campaign {campaign.pk} as completed in {db_name}")
                    
        except Exception as e:
            logger.error(f"[CELERY] Error cleaning {db_name}: {str(e)}")
            continue
    
    return f"Cleanup completed - {total_cleaned} campaigns updated"