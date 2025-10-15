# whatsapp_messaging/views.py

import json
import logging
import secrets # Import the secrets module for secure token generation
import requests
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseBadRequest, HttpRequest
from django.utils import timezone
from .models import WhatsAppInstance, WebhookEvent
from .forms import WhatsappInstanceForm
from .services.evolution_api import EvolutionAPIService


# Set up logging for the views
logger = logging.getLogger(__name__)


def _build_webhook_url(request, tenant_id):
    """
    Build the correct webhook URL for a tenant.
    Handles Docker, development, and production environments automatically.
    """
    # Check if SITE_URL is configured (production)
    if hasattr(settings, 'SITE_URL') and settings.SITE_URL:
        base_url = settings.SITE_URL
    else:
        # Auto-detect from request
        base_url = request.build_absolute_uri('/')
        # Remove trailing slash
        base_url = base_url.rstrip('/')
        
        # Docker environment detection: if using localhost/127.0.0.1, switch to Docker host IP
        if 'localhost:8000' in base_url or '127.0.0.1:8000' in base_url:
            # Evolution API in Docker needs to reach Django on host
            base_url = 'http://172.19.0.1:8000'
            logger.info(f"Detected Docker environment, using host IP: {base_url}")
    
    webhook_url = f"{base_url}/tenant/{tenant_id}/whatsapp/webhooks/evolution/"
    return webhook_url



# This view is for API-to-API communication.

@csrf_exempt
def webhook_handler(request: HttpRequest, tenant_id=None) -> JsonResponse:
    """
    Handles incoming webhook events from the WhatsApp API.
    Authenticates using instanceId from payload only.
    """
    if request.method != 'POST':
        return JsonResponse({"error": "Only POST requests are accepted"}, status=405)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        logger.error("Invalid JSON payload received.")
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # TEMPORARY DEBUG - Log the entire payload
    logger.info(f"========== WEBHOOK PAYLOAD DEBUG ==========")
    logger.info(f"Full payload: {json.dumps(payload, indent=2)}")
    logger.info(f"Payload keys: {payload.keys()}")
    logger.info(f"===========================================")

    # Get instance ID from payload - check multiple locations
    instance_id_from_payload = payload.get('data', {}).get('instanceId') or payload.get('instanceId')
    instance_name_from_payload = payload.get('instance')
    
    if not instance_id_from_payload and not instance_name_from_payload:
        logger.error("No instanceId or instance name in payload")
        return JsonResponse({"error": "Instance ID missing"}, status=401)

    # Find instance in tenant databases
    instance = None
    tenant_obj = None
    db_name = None
    
    from tenants.models import Tenant
    
    for tenant in Tenant.objects.all():
        db_name = f"crm_db_{tenant.tenant_id.replace('.', '_')}"
        try:
            # Try matching by external_id (UUID) first
            if instance_id_from_payload:
                try:
                    instance = WhatsAppInstance.objects.using(db_name).get(
                        external_id=instance_id_from_payload
                    )
                    tenant_obj = tenant
                    logger.info(f"Instance found by UUID: {instance.instance_name} in {db_name}")
                    break
                except WhatsAppInstance.DoesNotExist:
                    pass
            
            # Fallback: try matching by instance name
            if instance_name_from_payload and not instance:
                try:
                    instance = WhatsAppInstance.objects.using(db_name).get(
                        instance_name=instance_name_from_payload
                    )
                    tenant_obj = tenant
                    logger.info(f"Instance found by name: {instance.instance_name} in {db_name}")
                    break
                except WhatsAppInstance.DoesNotExist:
                    pass
                    
        except Exception as e:
            logger.error(f"Error querying tenant {tenant.tenant_id}: {e}")
            continue

    if not instance:
        logger.error(f"Instance not found - UUID: {instance_id_from_payload}, Name: {instance_name_from_payload}")
        return JsonResponse({"error": "Invalid Instance ID"}, status=401)

    event_type = payload.get('event')
    
    # Save webhook event in tenant database
    try:
        webhook_event = WebhookEvent.objects.using(db_name).create(
            whatsapp_instance=instance,
            event_type=event_type,
            payload=payload
        )
    except Exception as e:
        logger.error(f"Failed to save webhook event: {e}")
        webhook_event = None

    # Process different event types
    if event_type == 'qrcode.update' or event_type == 'QRCODE_UPDATED':
        qr_code = payload.get('data', {}).get('qrcode') or payload.get('qrcode')
        if qr_code:
            instance.qr_code = qr_code
            instance.save(using=db_name, update_fields=['qr_code'])
            logger.info(f"QR code updated for instance: {instance.instance_name}")
    
    elif event_type == 'connection.update' or event_type == 'CONNECTION_UPDATE':
        data = payload.get('data', {})
        connection_status = data.get('status') or data.get('state')
        if connection_status:
            if connection_status in ['connected', 'open']:
                instance.status = 'connected'
            elif connection_status in ['disconnected', 'close']:
                instance.status = 'disconnected'
            instance.save(using=db_name, update_fields=['status'])
            logger.info(f"Connection status updated to '{connection_status}'")
    
    elif event_type in ['messages.upsert', 'MESSAGES_UPSERT']:
        # Handle incoming messages
        try:
            data = payload.get('data', {})
            
            # Handle both formats
            if isinstance(data, list):
                messages_data = data
            else:
                messages_data = [data]
            
            for msg_data in messages_data:
                message_data = msg_data.get('message', {})
                key_data = msg_data.get('key', {})
                
                # Extract message details
                from_jid = key_data.get('remoteJid', '')
                from_number = from_jid.replace('@s.whatsapp.net', '').replace('@g.us', '')
                message_id = key_data.get('id', '')
                is_from_me = key_data.get('fromMe', False)
                
                # Extract message content
                message_text = ''
                message_type = 'text'
                media_url = None
                
                if 'conversation' in message_data:
                    message_text = message_data['conversation']
                elif 'extendedTextMessage' in message_data:
                    message_text = message_data['extendedTextMessage'].get('text', '')
                elif 'imageMessage' in message_data:
                    message_type = 'image'
                    message_text = message_data['imageMessage'].get('caption', 'Image received')
                elif 'documentMessage' in message_data:
                    message_type = 'document'
                    message_text = message_data['documentMessage'].get('fileName', 'Document received')
                elif 'audioMessage' in message_data:
                    message_type = 'audio'
                    message_text = 'Audio message received'
                elif 'videoMessage' in message_data:
                    message_type = 'video'
                    message_text = message_data['videoMessage'].get('caption', 'Video received')
                
                # Process only customer messages (not our own)
                if not is_from_me and from_number and message_text:
                    from marketing_campaigns.services.inbox_service import InboxService
                    
                    # Set database context for InboxService
                    from tenants.context import set_current_db
                    set_current_db(db_name)
                    
                    try:
                        conversation, message = InboxService.process_inbound_message(
                            tenant_id=tenant_obj.id,  # Use numeric tenant ID
                            whatsapp_instance_id=instance.id,
                            from_phone=from_number,
                            message_text=message_text,
                            message_type=message_type,
                            media_url=media_url,
                            evolution_message_id=message_id,
                            whatsapp_message_id=message_id
                        )
                        
                        if webhook_event:
                            webhook_event.processed = True
                            webhook_event.processed_at = timezone.now()
                            webhook_event.save(using=db_name)
                        
                        logger.info(f"Message processed - Conversation: {conversation.id}")
                        
                    except Exception as e:
                        logger.error(f"Failed to process message: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        if webhook_event:
                            webhook_event.processing_error = str(e)
                            webhook_event.save(using=db_name)
                
        except Exception as e:
            logger.error(f"Error processing message event: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    return JsonResponse({"ok": True})

# This view is for human-facing dashboards.
@login_required
def dashboard(request, tenant_id):
    """
    Displays a list of all WhatsApp instances for the current tenant.
    """
    if not request.tenant:
        messages.error(request, "Tenant not found.")
        return redirect('account_locked')

    # Use numeric tenant ID for database filtering
    instances = WhatsAppInstance.objects.filter(tenant_id=request.tenant.id).order_by('instance_name')
    return render(request, 'whatsapp_messaging/wa_dashboard.html', {
        'instances': instances,
        'tenant_id': request.tenant.tenant_id  # Use string tenant_id for URLs/templates
    })

@login_required
def add_instance(request, tenant_id):
    """
    Handles adding a new WhatsApp instance.
    """
    if not request.tenant:
        messages.error(request, "Tenant not found.")
        return redirect('account_locked')

    if request.method == 'POST':
        form = WhatsappInstanceForm(request.POST)
        if form.is_valid():
            instance = form.save(commit=False)
            
            # Automatically prefix with tenant identifier
            user_input_name = instance.instance_name
            instance.instance_name = f"{request.tenant.tenant_id}_{user_input_name}"
            
            # Use numeric tenant ID for database storage
            instance.tenant_id = request.tenant.id 
            
            instance.api_key = secrets.token_urlsafe(32)
            
            try:
                # Build tenant-aware webhook URL
                webhook_url = _build_webhook_url(request, request.tenant.tenant_id)
                
                api_url = f"{settings.EVOLUTION_API_CONFIG['BASE_URL']}/instance/create"
                headers = {
                    "apikey": settings.EVOLUTION_API_CONFIG['API_KEY'],
                    "Content-Type": "application/json"
                }
                payload = {
                    "instanceName": instance.instance_name,
                    "integration": "WHATSAPP-BAILEYS",
                    "webhook": {
                        "url": webhook_url,
                        "events": ["MESSAGES_UPSERT", "MESSAGES_UPDATE", "CONNECTION_UPDATE"]
                    }
                }

                logger.info(f"Creating instance: {instance.instance_name}")
                logger.info(f"Webhook URL: {webhook_url}")
                logger.info(f"API URL: {api_url}")
                logger.info(f"Payload: {payload}")
                
                response = requests.post(api_url, headers=headers, data=json.dumps(payload))
                logger.info(f"Response status: {response.status_code}")
                logger.info(f"Response body: {response.text}")     
                
                response.raise_for_status()
                
                evolution_response = response.json()
                if evolution_response.get('instance', {}).get('instanceId'):
                    instance.external_id = evolution_response.get('instance', {}).get('instanceId')
                    instance.save()
                    messages.success(request, f"WhatsApp instance '{instance.instance_name}' created successfully with webhook configured!")
                    return redirect('whatsapp_messaging:dashboard', tenant_id=request.tenant.tenant_id)
                else:
                    messages.error(request, f"Failed to create instance. API responded with: {evolution_response}")

            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to create Evolution API instance: {e}")
                messages.error(request, "A network error occurred. Please check your API base URL and key.")
            except Exception as e:
                logger.error(f"An unexpected error occurred: {e}")
                messages.error(request, "An unexpected error occurred. Please try again.")

        else:
            messages.error(request, "Failed to add instance. Please correct the errors in the form.")
    
    else:
        form = WhatsappInstanceForm()

    return render(request, 'whatsapp_messaging/add_instance.html', {
        'form': form,
        'tenant_id': request.tenant.tenant_id,
        'tenant_prefix': request.tenant.tenant_id
    })
    
    
@login_required
def edit_instance(request, tenant_id, pk):
    """
    Handles editing an existing WhatsApp instance.
    """
    # Use numeric tenant ID for database filtering
    instance = get_object_or_404(WhatsAppInstance, pk=pk, tenant_id=request.tenant.id)

    if request.method == 'POST':
        form = WhatsappInstanceForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, 'WhatsApp instance updated successfully!')
            # Use string tenant_id for URL redirect
            return redirect('whatsapp_messaging:dashboard', tenant_id=request.tenant.tenant_id)
    else:
        form = WhatsappInstanceForm(instance=instance)

    return render(request, 'whatsapp_messaging/edit_instance.html', {
        'form': form,
        'tenant_id': request.tenant.tenant_id  # Use string tenant_id for URLs/templates
    })

@login_required
def delete_instance(request, tenant_id, pk):
    """
    Handles deleting a WhatsApp instance from both CRM and Evolution API.
    """
    instance = get_object_or_404(WhatsAppInstance, pk=pk, tenant_id=request.tenant.id)
    
    if request.method == 'POST':
        # Try to delete from Evolution API first
        try:
            service = EvolutionAPIService()
            api_result = service.delete_instance(instance.instance_name)
            if not api_result['success']:
                logger.warning(f"Failed to delete from Evolution API: {api_result.get('error')}")
        except Exception as e:
            logger.error(f"Error deleting from Evolution API: {e}")
        
        # Delete from database regardless of API result
        instance_name = instance.instance_name
        instance.delete()
        messages.success(request, f'WhatsApp instance "{instance_name}" deleted successfully!')
        return redirect('whatsapp_messaging:dashboard', tenant_id=request.tenant.tenant_id)
    
    return render(request, 'whatsapp_messaging/confirm_delete.html', {
        'instance': instance, 
        'tenant_id': request.tenant.tenant_id
    })
    

@login_required
def sync_instances(request, tenant_id):
    """
    Sync WhatsApp instances with Evolution API
    """
    if not request.tenant:
        messages.error(request, "Tenant not found.")
        return redirect('account_locked')
    
    try:
        # Get all instances from Evolution API
        service = EvolutionAPIService()
        api_result = service.get_all_instances()
        
        if not api_result['success']:
            messages.error(request, f"Failed to sync: {api_result.get('error', 'Unknown error')}")
            return redirect('whatsapp_messaging:dashboard', tenant_id=request.tenant.tenant_id)
        
        api_instances = api_result['data']
        
        # Get current instances from database for this tenant
        db_instances = WhatsAppInstance.objects.filter(tenant_id=request.tenant.id)
        
        synced_count = 0
        deleted_count = 0
        
        # Create a map of Evolution API instances by name
        api_instance_map = {inst['name']: inst for inst in api_instances}
        
        # Update existing instances and mark for deletion if not in API
        for db_instance in db_instances:
            api_data = api_instance_map.get(db_instance.instance_name)
            
            if api_data:
                # Map Evolution API status to Django model status
                api_status = api_data.get('connectionStatus', 'disconnected')
                if api_status == 'open':
                    db_instance.status = 'connected'
                elif api_status == 'close':
                    db_instance.status = 'disconnected'
                elif api_status == 'connecting':
                    db_instance.status = 'connecting'
                else:
                    db_instance.status = 'disconnected'
                
                # Update owner JID
                db_instance.owner_jid = api_data.get('ownerJid')
                
                # Extract phone number from ownerJid if available
                if api_data.get('ownerJid'):
                    # ownerJid format: "60123456789@s.whatsapp.net"
                    phone = api_data.get('ownerJid').split('@')[0]
                    db_instance.phone_number = phone
                
                # Update profile information
                db_instance.profile_name = api_data.get('profileName')
                db_instance.profile_picture_url = api_data.get('profilePicUrl')
                
                # Update external ID if not set
                if not db_instance.external_id and api_data.get('id'):
                    db_instance.external_id = api_data.get('id')
                
                db_instance.save()
                synced_count += 1
                logger.info(f"Synced instance {db_instance.instance_name}: status={db_instance.status}, phone={db_instance.phone_number}")
                
            else:
                # Instance exists in DB but not in Evolution API - delete from DB
                logger.info(f"Deleting instance {db_instance.instance_name} - not found in Evolution API")
                db_instance.delete()
                deleted_count += 1
        
        # Create success message
        if synced_count > 0 or deleted_count > 0:
            message_parts = []
            if synced_count > 0:
                message_parts.append(f"{synced_count} instances synced")
            if deleted_count > 0:
                message_parts.append(f"{deleted_count} instances removed")
            messages.success(request, f"Sync completed: {', '.join(message_parts)}")
        else:
            messages.info(request, "All instances are already in sync")
            
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        messages.error(request, f"Sync failed: {str(e)}")
    
    return redirect('whatsapp_messaging:dashboard', tenant_id=request.tenant.tenant_id)



@login_required
def get_qr_code(request, tenant_id, pk):
    """
    Get and display QR code for WhatsApp instance connection
    """
    if not request.tenant:
        messages.error(request, "Tenant not found.")
        return redirect('account_locked')
    
    instance = get_object_or_404(WhatsAppInstance, pk=pk, tenant_id=request.tenant.id)
    
    try:
        service = EvolutionAPIService()
        result = service.get_qr_code(instance.instance_name)
        
        if result['success']:
            qr_data = result['data']
            # Update instance with QR code
            instance.qr_code = qr_data.get('base64', '')
            instance.save()
            
            context = {
                'instance': instance,
                'qr_code': qr_data.get('base64', ''),
                'tenant_id': request.tenant.tenant_id
            }
            return render(request, 'whatsapp_messaging/qr_code.html', context)
        else:
            messages.error(request, f"Failed to get QR code: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Error getting QR code: {e}")
        messages.error(request, "Failed to generate QR code")
    
    return redirect('whatsapp_messaging:dashboard', tenant_id=request.tenant.tenant_id)

@login_required
def send_test_message(request, tenant_id, pk):
    """
    Send a test message from WhatsApp instance
    """
    if not request.tenant:
        messages.error(request, "Tenant not found.")
        return redirect('account_locked')
    
    instance = get_object_or_404(WhatsAppInstance, pk=pk, tenant_id=request.tenant.id)
    
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')
        message_text = request.POST.get('message_text')
        
        if phone_number and message_text:
            try:
                service = EvolutionAPIService()
                result = service.send_text_message(instance.instance_name, phone_number, message_text)
                
                if result['success']:
                    messages.success(request, f"Message sent successfully to {phone_number}")
                else:
                    messages.error(request, f"Failed to send message: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                messages.error(request, "Failed to send message")
        else:
            messages.error(request, "Phone number and message are required")
    
    context = {
        'instance': instance,
        'tenant_id': request.tenant.tenant_id
    }
    return render(request, 'whatsapp_messaging/send_message.html', context)

@login_required
def anti_ban_settings(request, tenant_id):
    """View and edit anti-ban settings for tenant"""
    if not request.tenant:
        messages.error(request, "Tenant not found.")
        return redirect('account_locked')
    
    from marketing_campaigns.models import TenantCampaignSettings
    
    # FIXED: Pass tenant ID to get_instance()
    settings = TenantCampaignSettings.get_instance(request.tenant.id)
    
    if request.method == 'POST':
        try:
            # Update settings from form
            settings.instance_selection_strategy = request.POST.get('instance_selection_strategy', 'round_robin')
            settings.max_messages_per_hour_global = int(request.POST.get('max_messages_per_hour_global', 20))
            settings.max_messages_per_instance_hour = int(request.POST.get('max_messages_per_instance_hour', 10))
            settings.max_messages_per_instance_day = int(request.POST.get('max_messages_per_instance_day', 200))
            settings.min_delay_seconds = int(request.POST.get('min_delay_seconds', 60))
            settings.max_delay_seconds = int(request.POST.get('max_delay_seconds', 180))
            settings.use_random_delays = request.POST.get('use_random_delays') == 'on'
            settings.rotate_after_messages = int(request.POST.get('rotate_after_messages', 50))
            settings.instance_cooldown_minutes = int(request.POST.get('instance_cooldown_minutes', 15))
            settings.auto_disable_failed_instances = request.POST.get('auto_disable_failed_instances') == 'on'
            settings.failure_threshold = int(request.POST.get('failure_threshold', 5))
            
            settings.save()
            messages.success(request, "Anti-ban settings updated successfully!")
            return redirect('whatsapp_messaging:anti_ban_settings', tenant_id=request.tenant.tenant_id)
            
        except Exception as e:
            logger.error(f"Error saving anti-ban settings: {e}")
            messages.error(request, f"Error saving settings: {str(e)}")
    
    context = {
        'settings': settings,
        'tenant_id': request.tenant.tenant_id,
    }
    
    return render(request, 'whatsapp_messaging/anti_ban_settings.html', context)
