import requests
import json
import logging
import time
from django.conf import settings
from typing import Dict, List, Optional, Union
from datetime import datetime
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

class EvolutionAPIService:
    """Service for communicating with Evolution API"""
    
    def __init__(self):
        self.base_url = settings.EVOLUTION_API_CONFIG['BASE_URL']
        self.api_key = settings.EVOLUTION_API_CONFIG['API_KEY']
        self.timeout = settings.EVOLUTION_API_CONFIG.get('DEFAULT_TIMEOUT', 30)
        
        self.headers = {
            'Content-Type': 'application/json',
            'apikey': self.api_key
        }
        
        # Setup session with connection pooling and retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE"], 
            backoff_factor=1
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Make HTTP request to Evolution API with improved error handling"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Log request details for debugging
        logger.debug(f"Evolution API Request: {method} {url}")
        if data:
            logger.debug(f"Request payload: {json.dumps(data, indent=2)}")
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                timeout=self.timeout
            )
            
            logger.info(f"Evolution API {method} {endpoint}: {response.status_code}")
            
            # Accept multiple success status codes
            if response.status_code in [200, 201, 202]:
                try:
                    response_data = response.json()
                    logger.debug(f"Response data: {json.dumps(response_data, indent=2)}")
                    return {
                        'success': True,
                        'data': response_data,
                        'status_code': response.status_code
                    }
                except json.JSONDecodeError:
                    # Handle non-JSON responses
                    return {
                        'success': True,
                        'data': {'message': response.text},
                        'status_code': response.status_code
                    }
            else:
                error_message = response.text
                logger.error(f"Evolution API Error: {response.status_code} - {error_message}")
                
                # Try to parse error as JSON for better error messages
                try:
                    error_data = response.json()
                    error_message = error_data.get('message', error_message)
                except json.JSONDecodeError:
                    pass
                
                return {
                    'success': False,
                    'error': error_message,
                    'status_code': response.status_code,
                    'raw_response': response.text
                }
                
        except requests.exceptions.Timeout:
            logger.error(f"Evolution API Timeout: {method} {endpoint}")
            return {
                'success': False,
                'error': 'Request timeout - Evolution API is not responding',
                'status_code': 0
            }
        except requests.exceptions.ConnectionError:
            logger.error(f"Evolution API Connection Error: {method} {endpoint}")
            return {
                'success': False,
                'error': 'Connection error - Cannot reach Evolution API',
                'status_code': 0
            }
        except requests.RequestException as e:
            logger.error(f"Evolution API Request Exception: {str(e)}")
            return {
                'success': False,
                'error': f'Request failed: {str(e)}',
                'status_code': 0
            }
        except Exception as e:
            logger.error(f"Unexpected error in Evolution API request: {str(e)}")
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'status_code': 0
            }
    
    def create_instance(self, instance_name: str, webhook_url: str = None) -> Dict:
        """Create a new WhatsApp instance"""
        if not instance_name:
            return {
                'success': False,
                'error': 'Instance name is required',
                'status_code': 400
            }
        
        data = {
            'instanceName': instance_name,
            'integration': 'WHATSAPP-BAILEYS'
        }
        
        if webhook_url:
            data['webhook'] = {
                'url': webhook_url,
                'events': ['MESSAGES_UPSERT', 'MESSAGE_UPDATE', 'CONNECTION_UPDATE']
            }
        
        return self._make_request('POST', 'instance/create', data)
    
    def get_qr_code(self, instance_name: str) -> Dict:
        """Get QR code for WhatsApp authentication"""
        if not instance_name:
            return {
                'success': False,
                'error': 'Instance name is required',
                'status_code': 400
            }
        
        return self._make_request('GET', f'instance/connect/{instance_name}')
    
    def get_instance_status(self, instance_name: str) -> Dict:
        """Get connection status of an instance"""
        if not instance_name:
            return {
                'success': False,
                'error': 'Instance name is required',
                'status_code': 400
            }
        
        return self._make_request('GET', f'instance/connectionState/{instance_name}')
    
    def send_text_message(self, instance_name: str, phone: str, message: str) -> Dict:
        """Send text message via WhatsApp"""
        if not all([instance_name, phone, message]):
            return {
                'success': False,
                'error': 'Instance name, phone number, and message are required',
                'status_code': 400
            }
        
        # Clean phone number (remove any non-numeric characters except +)
        clean_phone = ''.join(char for char in phone if char.isdigit() or char == '+')
        
        data = {
            'number': clean_phone,
            'text': message
        }
        
        return self._make_request('POST', f'message/sendText/{instance_name}', data)
    
    def send_media_message(self, instance_name: str, phone: str, media_url: str, caption: str = "") -> Dict:
        """Send media message via WhatsApp"""
        if not all([instance_name, phone, media_url]):
            return {
                'success': False,
                'error': 'Instance name, phone number, and media URL are required',
                'status_code': 400
            }
        
        # Clean phone number
        clean_phone = ''.join(char for char in phone if char.isdigit() or char == '+')
        
        data = {
            'number': clean_phone,
            'mediaMessage': {
                'mediaUrl': media_url,
                'caption': caption
            }
        }
        
        return self._make_request('POST', f'message/sendMedia/{instance_name}', data)
    
    def get_all_instances(self) -> Dict:
        """Get all WhatsApp instances"""
        return self._make_request('GET', 'instance/fetchInstances')
    
    def delete_instance(self, instance_name: str) -> Dict:
        """Delete WhatsApp instance"""
        if not instance_name:
            return {
                'success': False,
                'error': 'Instance name is required',
                'status_code': 400
            }
        
        return self._make_request('DELETE', f'instance/delete/{instance_name}')
    
    def logout_instance(self, instance_name: str) -> Dict:
        """Logout WhatsApp instance"""
        if not instance_name:
            return {
                'success': False,
                'error': 'Instance name is required',
                'status_code': 400
            }
        
        return self._make_request('DELETE', f'instance/logout/{instance_name}')
    
    def get_instance_info(self, instance_name: str) -> Dict:
        """Get detailed information about an instance"""
        if not instance_name:
            return {
                'success': False,
                'error': 'Instance name is required',
                'status_code': 400
            }
        
        return self._make_request('GET', f'instance/{instance_name}')
    
    def restart_instance(self, instance_name: str) -> Dict:
        """Restart a WhatsApp instance"""
        if not instance_name:
            return {
                'success': False,
                'error': 'Instance name is required',
                'status_code': 400
            }
        
        return self._make_request('PUT', f'instance/restart/{instance_name}')
    
    def send_bulk_messages(self, instance_name: str, messages: List[Dict]) -> Dict:
        """Send multiple messages in bulk"""
        if not instance_name or not messages:
            return {
                'success': False,
                'error': 'Instance name and messages list are required',
                'status_code': 400
            }
        
        results = []
        success_count = 0
        failed_count = 0
        
        for message_data in messages:
            phone = message_data.get('phone')
            text = message_data.get('text')
            
            if not phone or not text:
                results.append({
                    'phone': phone,
                    'success': False,
                    'error': 'Phone and text are required'
                })
                failed_count += 1
                continue
            
            result = self.send_text_message(instance_name, phone, text)
            results.append({
                'phone': phone,
                'success': result['success'],
                'data': result.get('data'),
                'error': result.get('error')
            })
            
            if result['success']:
                success_count += 1
            else:
                failed_count += 1
            
            # Add small delay between messages to avoid rate limiting
            time.sleep(0.5)
        
        return {
            'success': True,
            'data': {
                'results': results,
                'summary': {
                    'total': len(messages),
                    'success': success_count,
                    'failed': failed_count
                }
            }
        }
    
    def health_check(self) -> Dict:
        """Check if Evolution API is healthy and responding"""
        try:
            result = self.get_all_instances()
            if result['success']:
                return {
                    'success': True,
                    'data': {
                        'status': 'healthy',
                        'instances_count': len(result['data']),
                        'timestamp': datetime.now().isoformat()
                    }
                }
            else:
                return {
                    'success': False,
                    'error': 'API is not responding correctly',
                    'data': result
                }
        except Exception as e:
            return {
                'success': False,
                'error': f'Health check failed: {str(e)}'
            }
    
    def close(self):
        """Close the session and clean up resources"""
        if hasattr(self, 'session'):
            self.session.close()

# Test function with improved error handling
def test_evolution_api_service() -> bool:
    """Test function to verify Evolution API service works"""
    service = EvolutionAPIService()
    
    try:
        # Test health check first
        health_result = service.health_check()
        if not health_result['success']:
            print(f"Evolution API health check failed: {health_result['error']}")
            return False
        
        print("Evolution API Service is healthy!")
        print(f"Found {health_result['data']['instances_count']} instances")
        return True
        
    except Exception as e:
        print(f"Evolution API Service test failed: {str(e)}")
        return False
    finally:
        service.close()