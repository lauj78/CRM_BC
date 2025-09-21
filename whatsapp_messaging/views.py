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
from .models import WhatsAppInstance, WebhookEvent
from .forms import WhatsappInstanceForm
from .services.evolution_api import EvolutionAPIService


# Set up logging for the views
logger = logging.getLogger(__name__)

# This view is for API-to-API communication.
@csrf_exempt
def webhook_handler(request: HttpRequest) -> JsonResponse:
    """
    Handles incoming webhook events from the WhatsApp API.
    Uses the unique instance API key for validation.
    """
    if request.method != 'POST':
        return JsonResponse({"error": "Only POST requests are accepted"}, status=405)

    try:
        payload = json.loads(request.body)
        logger.info(f"Received webhook payload: {payload}")

    except json.JSONDecodeError:
        logger.error("Invalid JSON payload received.")
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # This is the secret API key generated for each instance
    api_key_header = request.headers.get('x-api-key')
    instance_id_from_payload = payload.get('instanceId')

    if not api_key_header or not instance_id_from_payload:
        logger.warning("Missing API key or instance ID in webhook request.")
        return JsonResponse({"error": "API Key or Instance ID missing"}, status=401)

    try:
        # We need a model named `WhatsappInstance` to perform this lookup.
        # The secret key is used here to validate the webhook and link it to a specific tenant.
        instance = WhatsAppInstance.objects.get(
            external_id=instance_id_from_payload,
            api_key=api_key_header
        )
        logger.info(f"Webhook request validated for instance: {instance.instance_name}")

    except WhatsAppInstance.DoesNotExist:
        logger.error(f"Invalid API key or instance ID for instance: {instance_id_from_payload}")
        return JsonResponse({"error": "Invalid API Key or Instance ID"}, status=401)

    event_type = payload.get('event')
    
    # Save the webhook event to a database table if needed.
    try:
        WebhookEvent.objects.create(
            whatsapp_instance=instance,
            event_type=event_type,
            payload=payload
        )
    except Exception as e:
        logger.error(f"Failed to save webhook event: {e}")
        pass

    if event_type == 'qrcode.update':
        qr_code = payload.get('data', {}).get('qrcode')
        if qr_code:
            instance.qr_code = qr_code
            instance.save(update_fields=['qr_code'])
            logger.info(f"QR code updated for instance: {instance.instance_name}")
    
    elif event_type == 'connection.update':
        connection_status = payload.get('data', {}).get('status')
        if connection_status:
            if connection_status == 'connected':
                instance.status = 'connected'
            elif connection_status == 'disconnected':
                instance.status = 'disconnected'
            instance.save(update_fields=['status'])
            logger.info(f"Connection status updated to '{connection_status}' for instance: {instance.instance_name}")
    
    # We will need to add more event handlers here for incoming messages, etc.
    
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
                api_url = f"{settings.EVOLUTION_API_CONFIG['BASE_URL']}/instance/create"
                headers = {
                    "apikey": settings.EVOLUTION_API_CONFIG['API_KEY'],
                    "Content-Type": "application/json"
                }
                payload = {
                    "instanceName": instance.instance_name,  # This now includes prefix
                    "integration": "WHATSAPP-BAILEYS",
                    "webhook": {
                        "url": f"{settings.EVOLUTION_API_CONFIG['WEBHOOK_URL']}?apiKey={instance.api_key}",
                        "events": ["MESSAGES_UPSERT", "MESSAGE_UPDATE", "CONNECTION_UPDATE"]
                    }
                }

                logger.info(f"API URL: {api_url}")
                logger.info(f"Headers: {headers}")
                logger.info(f"Payload: {payload}")
                
                response = requests.post(api_url, headers=headers, data=json.dumps(payload))
                logger.info(f"Response status: {response.status_code}")
                logger.info(f"Response body: {response.text}")     
                
                response.raise_for_status()
                
                evolution_response = response.json()
                if evolution_response.get('instance', {}).get('instanceId'):
                    instance.external_id = evolution_response.get('instance', {}).get('instanceId')
                    instance.save()
                    messages.success(request, f"WhatsApp instance '{instance.instance_name}' created successfully!")
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
        'tenant_prefix': request.tenant.tenant_id  # Pass to template for display
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
                # Update instance with latest data from API
                db_instance.status = api_data.get('connectionStatus', 'disconnected')
                db_instance.owner_jid = api_data.get('ownerJid')
                db_instance.profile_name = api_data.get('profileName')
                db_instance.profile_picture_url = api_data.get('profilePicUrl')
                db_instance.save()
                synced_count += 1
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
        messages.error(request, "Sync failed due to an unexpected error")
    
    return redirect('whatsapp_messaging:dashboard', tenant_id=request.tenant.tenant_id)