# whatsapp_messaging/whatsapp_verification.py

import requests
import logging
from django.conf import settings
from django.utils import timezone
from marketing_campaigns.models import PhoneNumberHistory
from whatsapp_messaging.models import WhatsAppInstance
from tenants.context import set_current_db, clear_current_db, get_current_db
import time

logger = logging.getLogger('whatsapp_messaging')

class WhatsAppVerificationService:
    """Service to verify if phone numbers have WhatsApp accounts using Evolution API - Multi-tenant aware"""
    
    def __init__(self, tenant_id, database_alias=None):
        self.tenant_id = tenant_id
        self.database_alias = database_alias or self._get_database_for_tenant(tenant_id)
        self.config = settings.EVOLUTION_API_CONFIG
        self.base_url = self.config['BASE_URL']
        self.api_key = self.config['API_KEY']
        self.headers = {
            'apikey': self.api_key,
            'Content-Type': 'application/json'
        }
        
        logger.info(f"WhatsApp verification service initialized for tenant {tenant_id}, database: {self.database_alias}")
    
    def _set_tenant_context(self):
        """Set tenant database context for this thread"""
        set_current_db(self.database_alias)
        logger.debug(f"Set tenant context to database: {self.database_alias}")
    
    def _clear_tenant_context(self):
        """Clear tenant database context"""
        clear_current_db()
        logger.debug("Cleared tenant context")
    
    def _get_database_for_tenant(self, tenant_id):
        """Map tenant_id to database alias based on your routing logic"""
        if tenant_id == 2:  # pukul.com tenant
            return 'crm_db_pukul_com'
        elif tenant_id == 3:  # test.com tenant (if you have one)
            return 'crm_db_test_com'  
        else:
            return 'default'  # Default database
    
    def verify_single_number(self, phone_number, instance_name=None):
        """Verify a single phone number and update history"""
        
        # Set tenant context for this operation
        self._set_tenant_context()
        
        try:
            if not instance_name:
                # Get first active instance for this tenant (should now use tenant database)
                instance = WhatsAppInstance.objects.filter(
                    tenant_id=self.tenant_id, 
                    is_active=True
                ).first()
                
                if not instance:
                    logger.error(f"No active WhatsApp instances found for tenant {self.tenant_id}")
                    return False, "no_instances", None
                instance_name = instance.instance_name
            
            # Evolution API call (same as before)
            url = f"{self.base_url}/chat/whatsappNumbers/{instance_name}"
            clean_number = phone_number.replace('+', '')
            payload = {"numbers": [clean_number]}
            
            logger.info(f"Checking WhatsApp status for {phone_number} using instance {instance_name} (tenant {self.tenant_id})")
            response = requests.post(url, json=payload, headers=self.headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                if data and len(data) > 0:
                    result = data[0]
                    exists = result.get('exists', False)
                    
                    # Update phone history (should now use tenant database due to context)
                    history = self._update_phone_history(phone_number, exists, None)
                    
                    status = "confirmed" if exists else "not_available"
                    logger.info(f"WhatsApp check for {phone_number}: {status.upper()}")
                    return exists, status, history
                else:
                    logger.warning(f"Empty response for {phone_number}")
                    history = self._update_phone_history(phone_number, False, "empty_response")
                    return False, "empty_response", history
            else:
                logger.error(f"API error {response.status_code} for {phone_number}: {response.text}")
                error_reason = f"api_error_{response.status_code}"
                history = self._update_phone_history(phone_number, False, error_reason)
                return False, error_reason, history
                
        except requests.Timeout:
            logger.error(f"Timeout checking {phone_number}")
            history = self._update_phone_history(phone_number, False, "timeout")
            return False, "timeout", history
        except requests.RequestException as e:
            logger.error(f"Request error checking {phone_number}: {str(e)}")
            history = self._update_phone_history(phone_number, False, "request_error")
            return False, "request_error", history
        except Exception as e:
            logger.error(f"Unexpected error checking {phone_number}: {str(e)}")
            history = self._update_phone_history(phone_number, False, "unexpected_error")
            return False, "unexpected_error", history
        finally:
            # Always clear context when done
            self._clear_tenant_context()
    
    def get_available_instances(self):
        """Get list of available instances for this tenant"""
        self._set_tenant_context()
        try:
            instances = WhatsAppInstance.objects.filter(
                tenant_id=self.tenant_id,
                is_active=True
            )
            return list(instances.values_list('instance_name', flat=True))
        finally:
            self._clear_tenant_context()
    
    def verify_audience_numbers(self, audience, delay_seconds=3):
        """Verify all numbers in an audience and flag problematic ones"""
        
        if not audience.members:
            return {"verified": 0, "not_found": 0, "errors": [], "flagged": 0, "total": 0}
        
        results = {
            "verified": 0,
            "not_found": 0, 
            "errors": [],
            "flagged": 0,
            "total": len(audience.members)
        }
        
        # Get available instances for rotation (tenant-specific)
        instances = self.get_available_instances()
        if not instances:
            results["errors"].append(f"No active WhatsApp instances available for tenant {self.tenant_id}")
            return results
        
        current_instance_idx = 0
        
        logger.info(f"Starting WhatsApp verification for audience '{audience.name}' ({results['total']} numbers) using tenant {self.tenant_id} instances: {instances}")
        
        # Verify each number
        for i, member in enumerate(audience.members):
            phone_number = member.get('phone_number')
            if not phone_number:
                continue
            
            # Rotate instances to avoid rate limits
            instance_name = instances[current_instance_idx % len(instances)]
            current_instance_idx += 1
            
            # Check if we already have recent history for this number
            try:
                existing_history = PhoneNumberHistory.objects.get(phone_number=phone_number)
                # If checked within last 7 days and status is known, skip verification
                if (existing_history.whatsapp_status in ['confirmed', 'not_available'] and 
                    existing_history.updated_at and 
                    (timezone.now() - existing_history.updated_at).days < 7):
                    
                    logger.info(f"Using cached WhatsApp status for {phone_number}: {existing_history.whatsapp_status}")
                    
                    # Update member data with cached info
                    if existing_history.whatsapp_status == 'confirmed':
                        results["verified"] += 1
                        member['whatsapp_verified'] = True
                        member['whatsapp_status'] = 'confirmed'
                    else:
                        results["not_found"] += 1
                        member['whatsapp_verified'] = True
                        member['whatsapp_status'] = 'not_available'
                    
                    # Check if flagged
                    if existing_history.is_flagged or existing_history.risk_level == 'high':
                        member['is_flagged'] = True
                        member['flag_reason'] = f"Risk: {existing_history.risk_level}, Success: {existing_history.success_rate}%"
                        results["flagged"] += 1
                    
                    continue  # Skip API call
                    
            except PhoneNumberHistory.DoesNotExist:
                pass  # Will verify via API
            
            # Verify number via API
            exists, status, history = self.verify_single_number(phone_number, instance_name)
            
            # Update member data
            member['whatsapp_verified'] = True
            member['whatsapp_status'] = status
            member['last_verified'] = timezone.now().isoformat()
            
            if status == "confirmed":
                results["verified"] += 1
            elif status == "not_available":
                results["not_found"] += 1
            else:
                results["errors"].append(f"{phone_number}: {status}")
            
            # Check if number should be flagged
            if history and (history.is_flagged or history.risk_level == 'high'):
                member['is_flagged'] = True
                member['flag_reason'] = f"Risk: {history.risk_level}"
                if history.total_attempts > 0:
                    member['flag_reason'] += f", Success: {history.success_rate}%"
                results["flagged"] += 1
            
            # Rate limiting delay
            time.sleep(delay_seconds)
            
            # Progress logging
            if (i + 1) % 5 == 0:
                logger.info(f"Verified {i + 1}/{results['total']} numbers...")
        
        # Save updated audience data
        audience.save(update_fields=['members'])
        
        logger.info(f"WhatsApp verification completed: {results['verified']} confirmed, {results['not_found']} not found, {results['flagged']} flagged, {len(results['errors'])} errors")
        return results
    
    def _update_phone_history(self, phone_number, whatsapp_exists, error_reason):
        """Update or create phone number history record (uses tenant database due to context)"""
        
        history, created = PhoneNumberHistory.objects.get_or_create(
            phone_number=phone_number,
            defaults={
                'country_code': self._detect_country_from_phone(phone_number)
            }
        )
        
        # Update WhatsApp status
        if whatsapp_exists:
            history.whatsapp_status = 'confirmed'
        elif error_reason:
            history.whatsapp_status = 'unknown'
            # Add error reason to failure reasons if not API-related
            if error_reason not in ['timeout', 'request_error', 'api_error_500']:
                if error_reason not in history.failure_reasons:
                    history.failure_reasons.append(error_reason)
        else:
            history.whatsapp_status = 'not_available'
            # Track "not on whatsapp" failures
            if 'not_on_whatsapp' not in history.failure_reasons:
                history.failure_reasons.append('not_on_whatsapp')
        
        # Update timestamp
        history.updated_at = timezone.now()
        
        history.save()
        
        logger.debug(f"Updated phone history for {phone_number} in database: {get_current_db()}")
        return history
    
    def _detect_country_from_phone(self, phone_number):
        """Simple country detection from phone number"""
        if phone_number.startswith('+60'):
            return 'MY'
        elif phone_number.startswith('+62'):
            return 'ID'
        elif phone_number.startswith('+855'):
            return 'KH'
        elif phone_number.startswith('+66'):
            return 'TH'
        elif phone_number.startswith('+65'):
            return 'SG'
        elif phone_number.startswith('+63'):
            return 'PH'
        else:
            return 'UNKNOWN'