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
from tenants.context import set_current_db, clear_current_db

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
    Kick off continuous campaign message processing
    This just starts the first message - chaining handles the rest
    """
    logger.info(f"[CELERY] Starting continuous processing for campaign {campaign_id}")
    
    try:
        # Auto-detect and set tenant context
        db_alias = _set_tenant_context_for_campaign(campaign_id)
        if not db_alias:
            return f"Campaign {campaign_id} not found"
        
        campaign = Campaign.objects.get(pk=campaign_id)
        
        if campaign.status != 'running':
            logger.warning(f"[CELERY] Campaign {campaign_id} is not running (status: {campaign.status})")
            return f"Campaign not running: {campaign.status}"
        
        # Get first queued target
        first_target = campaign.targets.filter(status='queued').first()
        
        if not first_target:
            logger.info(f"[CELERY] No pending targets for campaign {campaign_id}")
            
            # Check if campaign is complete
            remaining = campaign.targets.filter(status__in=['queued', 'scheduled', 'sending']).count()
            if remaining == 0:
                campaign.status = 'completed'
                campaign.save()
                logger.info(f"[CELERY] Campaign {campaign_id} marked as completed")
            
            return "No pending targets"
        
        # Start the chain by sending first message
        logger.info(f"[CELERY] Starting continuous chain with target {first_target.pk}")
        send_single_message.delay(first_target.pk, campaign_id)
        
        return f"Started continuous processing for campaign {campaign_id}"
        
    except Campaign.DoesNotExist:
        logger.error(f"[CELERY] Campaign {campaign_id} not found")
        return f"Campaign {campaign_id} not found"
    except Exception as e:
        logger.error(f"[CELERY] Error starting campaign {campaign_id}: {str(e)}")
        raise self.retry(countdown=300, exc=e)


@shared_task(bind=True, max_retries=3)
def send_single_message(self, target_id, campaign_id=None):
    """
    Send a single message and chain to the next one
    """
    logger.info(f"[CELERY] Sending message to target {target_id}")
    
    try:
        # Auto-detect and set tenant context
        db_alias = _set_tenant_context_for_target(target_id)
        if not db_alias:
            return f"Target {target_id} not found in any database"
        
        with transaction.atomic():
            # Get target and campaign
            target = CampaignTarget.objects.get(pk=target_id)
            campaign = Campaign.objects.get(pk=target.campaign_id)
            
            # Store campaign_id for chaining if not provided
            if campaign_id is None:
                campaign_id = campaign.pk
            
            if target.status != 'queued':
                logger.warning(f"[CELERY] Target {target_id} status is {target.status}, skipping")
                # Still chain to next even if this one skipped
                _chain_to_next_target(campaign_id, campaign)
                return f"Target not queued: {target.status}"
            
            # Update target status
            target.status = 'sending'
            target.save()
            
            # Get campaign template
            campaign_message = campaign.campaign_messages.first()
            if not campaign_message:
                raise Exception("No template found for campaign")
            
            template = MessageTemplate.objects.get(pk=campaign_message.template_id)
            rendered_message = template.render_message(target.member_data)
            
            # Use anti-ban service for instance selection
            from marketing_campaigns.services import AntiBanService
            
            tenant_id = getattr(campaign, 'tenant_id', None) or 2
            anti_ban_service = AntiBanService(tenant_id=tenant_id)
            
            # Select best instance using anti-ban strategy
            whatsapp_instance = anti_ban_service.select_instance_for_campaign(campaign)
            
            if not whatsapp_instance:
                logger.warning(f"[CELERY] No available instance, will retry target {target_id} in 10 minutes")
                # Requeue target
                target.status = 'queued'
                target.save()
                
                # Retry this same target after 10 minutes
                send_single_message.apply_async(
                    args=[target_id, campaign_id],
                    countdown=600  # 10 minutes
                )
                return "No instance available, scheduled retry"
            
            # Check if instance can send now
            can_send, reason = anti_ban_service.can_send_now(whatsapp_instance)
            if not can_send:
                logger.warning(f"[CELERY] Instance cannot send: {reason}")
                target.status = 'queued'
                target.save()
                
                # Retry after delay
                send_single_message.apply_async(
                    args=[target_id, campaign_id],
                    countdown=300  # 5 minutes
                )
                return f"Instance unavailable: {reason}"
            
            # Send message via Evolution API
            service = EvolutionAPIService()
            result = service.send_text_message(
                instance_name=whatsapp_instance.instance_name,
                phone=target.phone_number,
                message=rendered_message
            )
            
            # Record result with anti-ban service
            if result['success']:
                target.status = 'sent'
                target.sent_at = timezone.now()
                target.final_message = rendered_message
                target.whatsapp_instance = whatsapp_instance.instance_name
                target.evolution_api_response = result
                
                campaign.total_sent += 1
                campaign.save()
                
                anti_ban_service.record_message_sent(whatsapp_instance, success=True)
                
                logger.info(f"[CELERY] Successfully sent message to {target.phone_number} via {whatsapp_instance.instance_name}")
                
            else:
                target.status = 'failed'
                target.error_message = result.get('error', 'Unknown error')
                target.retry_count += 1
                target.evolution_api_response = result
                
                campaign.total_failed += 1
                campaign.save()
                
                anti_ban_service.record_message_sent(
                    whatsapp_instance, 
                    success=False, 
                    error_message=target.error_message
                )
                
                logger.error(f"[CELERY] Failed to send message to {target.phone_number}: {target.error_message}")
                
                # Retry if under limit
                if target.retry_count < campaign.max_retry_per_number:
                    target.status = 'queued'
                    logger.info(f"[CELERY] Queued target {target_id} for retry ({target.retry_count}/{campaign.max_retry_per_number})")
            
            target.save()
        
        # CHAIN TO NEXT TARGET
        _chain_to_next_target(campaign_id, campaign, anti_ban_service)
        
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
        
        # Don't retry via Celery retry - let chaining handle it
        if campaign_id:
            _chain_to_next_target(campaign_id, None)
        
        return f"Error: {str(e)}"


def _chain_to_next_target(campaign_id, campaign=None, anti_ban_service=None):
    """
    Chain to the next queued target with appropriate delay
    """
    try:
        if campaign is None:
            campaign = Campaign.objects.get(pk=campaign_id)
        
        # Check if campaign is still running
        if campaign.status != 'running':
            logger.info(f"[CELERY] Campaign {campaign_id} is no longer running, stopping chain")
            return
        
        # Get next queued target
        next_target = campaign.targets.filter(status='queued').first()
        
        if not next_target:
            logger.info(f"[CELERY] No more queued targets for campaign {campaign_id}")
            
            # Check if campaign is complete
            remaining = campaign.targets.filter(status__in=['queued', 'scheduled', 'sending']).count()
            if remaining == 0:
                campaign.status = 'completed'
                campaign.save()
                logger.info(f"[CELERY] Campaign {campaign_id} completed")
            
            return
        
        # Calculate delay using anti-ban service
        if anti_ban_service is None:
            from marketing_campaigns.services import AntiBanService
            tenant_id = getattr(campaign, 'tenant_id', None) or 2
            anti_ban_service = AntiBanService(tenant_id=tenant_id)
        
        delay_seconds = anti_ban_service.calculate_next_delay(campaign)
        
        logger.info(f"[CELERY] Chaining to next target {next_target.pk} with {delay_seconds}s delay")
        
        # Schedule next message
        send_single_message.apply_async(
            args=[next_target.pk, campaign_id],
            countdown=delay_seconds
        )
        
    except Exception as e:
        logger.error(f"[CELERY] Error chaining to next target: {str(e)}")

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


@shared_task(bind=True, max_retries=2)
def verify_audience_whatsapp_task(self, audience_id, tenant_id, database_alias=None):
    """
    Background task to verify WhatsApp numbers in an audience
    
    Args:
        audience_id: ID of the CustomAudience to verify
        tenant_id: Tenant ID for the verification service
        database_alias: Which database to use (auto-detected if None)
    """
    
    # Auto-detect database if not provided
    if database_alias is None:
        if tenant_id == 2:
            database_alias = 'crm_db_pukul_com'
        elif tenant_id == 3:
            database_alias = 'crm_db_test_com'
        else:
            database_alias = 'default'
    
    # Set tenant context for database routing
    set_current_db(database_alias)
    
    try:
        from marketing_campaigns.models import CustomAudience
        from whatsapp_messaging.whatsapp_verification import WhatsAppVerificationService
        
        logger.info(f"Starting WhatsApp verification task for audience {audience_id}, tenant {tenant_id}, database {database_alias}")
        
        # Get the audience
        try:
            audience = CustomAudience.objects.get(pk=audience_id)
        except CustomAudience.DoesNotExist:
            logger.error(f"Audience {audience_id} not found in database {database_alias}")
            return {
                'success': False,
                'error': f'Audience {audience_id} not found',
                'audience_id': audience_id
            }
        
        # Update status to in_progress
        audience.whatsapp_verification_status = 'in_progress'
        audience.verification_started_at = timezone.now()
        audience.save(using=database_alias, update_fields=[
            'whatsapp_verification_status', 
            'verification_started_at'
        ])
        
        logger.info(f"Audience '{audience.name}' verification started with {audience.total_numbers} numbers")
        
        # Initialize verification service
        verifier = WhatsAppVerificationService(tenant_id=tenant_id, database_alias=database_alias)
        
        # Get verification settings
        delay_seconds = 3  # Default delay
        retry_failed = True  # Retry failed numbers once
        
        # Track progress
        total_numbers = len(audience.members) if audience.members else 0
        if total_numbers == 0:
            logger.warning(f"Audience {audience_id} has no members to verify")
            audience.whatsapp_verification_status = 'completed'
            audience.verification_completed_at = timezone.now()
            audience.save(using=database_alias, update_fields=[
                'whatsapp_verification_status', 
                'verification_completed_at'
            ])
            return {
                'success': True,
                'message': 'No numbers to verify',
                'audience_id': audience_id,
                'total': 0
            }
        
        # Verify numbers with progress tracking
        results = {
            'verified': 0,
            'not_found': 0,
            'errors': [],
            'flagged': 0,
            'total': total_numbers,
            'processed': 0
        }
        
        # Get available instances for rotation
        instances = verifier.get_available_instances()
        if not instances:
            raise Exception(f"No active WhatsApp instances available for tenant {tenant_id}")
        
        current_instance_idx = 0
        
        logger.info(f"Using {len(instances)} WhatsApp instances: {instances}")
        
        # Process each member
        for i, member in enumerate(audience.members):
            phone_number = member.get('phone_number')
            if not phone_number:
                results['processed'] += 1
                continue
            
            # Check for cached verification (14 days) with proper database routing
            cached_result = check_cached_verification(phone_number, audience.verification_cache_days, database_alias)
            if cached_result:
                # Use cached result
                member.update(cached_result)
                if cached_result['whatsapp_status'] == 'confirmed':
                    results['verified'] += 1
                elif cached_result['whatsapp_status'] == 'not_available':
                    results['not_found'] += 1
                
                logger.debug(f"Using cached result for {phone_number}: {cached_result['whatsapp_status']}")
            else:
                # Verify via API
                instance_name = instances[current_instance_idx % len(instances)]
                current_instance_idx += 1
                
                try:
                    exists, status, history = verifier.verify_single_number(phone_number, instance_name)
                    
                    # Update member data
                    member['whatsapp_verified'] = True
                    member['whatsapp_status'] = status
                    member['last_verified'] = timezone.now().isoformat()
                    
                    if status == "confirmed":
                        results['verified'] += 1
                    elif status == "not_available":
                        results['not_found'] += 1
                    else:
                        results['errors'].append(f"{phone_number}: {status}")
                    
                    # Check if flagged
                    if history and (history.is_flagged or history.risk_level == 'high'):
                        member['is_flagged'] = True
                        member['flag_reason'] = f"Risk: {history.risk_level}"
                        results['flagged'] += 1
                    
                    logger.debug(f"Verified {phone_number}: {status}")
                    
                except Exception as verify_error:
                    logger.error(f"Error verifying {phone_number}: {str(verify_error)}")
                    results['errors'].append(f"{phone_number}: verification_error")
                    member['whatsapp_status'] = 'unknown'
                    member['whatsapp_verified'] = False
                
                # Rate limiting delay
                time.sleep(delay_seconds)
            
            results['processed'] += 1
            
            # Update progress every 10 numbers
            if (i + 1) % 10 == 0:
                # Save intermediate progress
                audience.save(using=database_alias, update_fields=['members'])
                
                # Update stats manually with explicit database
                audience.whatsapp_verified_count = results['verified']
                audience.whatsapp_not_found_count = results['not_found']
                audience.whatsapp_error_count = len(results['errors'])
                audience.whatsapp_pending_count = total_numbers - results['processed']
                
                audience.save(using=database_alias, update_fields=[
                    'whatsapp_verified_count', 'whatsapp_not_found_count',
                    'whatsapp_error_count', 'whatsapp_pending_count'
                ])
                
                progress_pct = round((results['processed'] / total_numbers) * 100, 1)
                logger.info(f"Verification progress: {results['processed']}/{total_numbers} ({progress_pct}%)")
                
                # Update task progress for monitoring
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'processed': results['processed'],
                        'total': total_numbers,
                        'verified': results['verified'],
                        'not_found': results['not_found'],
                        'errors': len(results['errors'])
                    }
                )
        
        # Final save and stats update
        audience.save(using=database_alias, update_fields=['members'])
        audience.verification_completed_at = timezone.now()
        
        # Explicit stats update with database routing
        audience.whatsapp_verified_count = results['verified']
        audience.whatsapp_not_found_count = results['not_found']  
        audience.whatsapp_error_count = len(results['errors'])
        audience.whatsapp_pending_count = total_numbers - results['processed']
        audience.whatsapp_verification_status = 'completed'
        
        audience.save(using=database_alias, update_fields=[
            'whatsapp_verified_count', 'whatsapp_not_found_count',
            'whatsapp_error_count', 'whatsapp_pending_count', 
            'whatsapp_verification_status', 'verification_completed_at'
        ])
        
        # Log final results
        logger.info(f"WhatsApp verification completed for audience '{audience.name}': "
                   f"{results['verified']} confirmed, {results['not_found']} not found, "
                   f"{results['flagged']} flagged, {len(results['errors'])} errors")
        
        return {
            'success': True,
            'audience_id': audience_id,
            'audience_name': audience.name,
            'results': results,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"WhatsApp verification task failed for audience {audience_id}: {str(e)}")
        
        # Update audience status to failed
        try:
            from marketing_campaigns.models import CustomAudience
            audience = CustomAudience.objects.get(pk=audience_id)
            audience.whatsapp_verification_status = 'failed'
            audience.save(using=database_alias, update_fields=['whatsapp_verification_status'])
        except Exception as update_error:
            logger.error(f"Failed to update audience status: {str(update_error)}")
        
        # Retry logic
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying verification task in 60 seconds (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60, exc=e)
        
        return {
            'success': False,
            'error': str(e),
            'audience_id': audience_id
        }
    
    finally:
        # Always clear tenant context
        clear_current_db()


def check_cached_verification(phone_number, cache_days=14, database_alias=None):
    """
    Check if we have recent verification data for a phone number
    
    Returns cached data if found and still valid, None otherwise
    """
    try:
        from marketing_campaigns.models import PhoneNumberHistory
        from django.utils import timezone
        
        logger.debug(f"Checking cache for {phone_number} in database {database_alias}")
        
        # FIXED: Use explicit database query
        if database_alias:
            history = PhoneNumberHistory.objects.using(database_alias).get(phone_number=phone_number)
        else:
            history = PhoneNumberHistory.objects.get(phone_number=phone_number)
        
        logger.debug(f"Found history for {phone_number}: status={history.whatsapp_status}, updated={history.updated_at}")
        
        # Check if verification is recent enough
        if history.updated_at:
            days_ago = (timezone.now() - history.updated_at).days
            hours_ago = (timezone.now() - history.updated_at).total_seconds() / 3600
            
            cache_valid = (days_ago <= cache_days and 
                          history.whatsapp_status in ['confirmed', 'not_available'])
            
            logger.debug(f"Cache check for {phone_number}: days_ago={days_ago}, hours_ago={hours_ago:.1f}, cache_days={cache_days}, status={history.whatsapp_status}, valid={cache_valid}")
            
            if cache_valid:
                logger.info(f"Using cached verification for {phone_number}: {history.whatsapp_status} (age: {hours_ago:.1f} hours)")
                return {
                    'whatsapp_verified': True,
                    'whatsapp_status': history.whatsapp_status,
                    'last_verified': history.updated_at.isoformat(),
                    'is_flagged': history.is_flagged or history.risk_level == 'high',
                    'flag_reason': f"Risk: {history.risk_level}, Success: {history.success_rate}%" if history.is_flagged else None
                }
            else:
                logger.debug(f"Cache expired/invalid for {phone_number}: age {days_ago} days, status {history.whatsapp_status}")
        else:
            logger.debug(f"No updated_at timestamp for {phone_number}")
        
        return None
        
    except PhoneNumberHistory.DoesNotExist:
        logger.debug(f"No phone history found for {phone_number} in database {database_alias}")
        return None
    except Exception as e:
        logger.error(f"Error checking cache for {phone_number}: {str(e)}")
        return None


@shared_task
def cleanup_old_verification_data():
    """
    Periodic task to clean up old phone number verification data
    Run this daily to keep database size manageable
    """
    from marketing_campaigns.models import PhoneNumberHistory
    from django.utils import timezone
    from datetime import timedelta
    
    # Delete verification data older than 90 days
    cutoff_date = timezone.now() - timedelta(days=90)
    deleted_count = PhoneNumberHistory.objects.filter(
        updated_at__lt=cutoff_date,
        is_flagged=False  # Keep flagged numbers longer
    ).delete()[0]
    
    logger.info(f"Cleaned up {deleted_count} old phone verification records")
    return {'deleted_count': deleted_count}