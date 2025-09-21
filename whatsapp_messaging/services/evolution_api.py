import requests
import json
import logging
from django.conf import settings
from typing import Dict, List, Optional
from datetime import datetime

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
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Make HTTP request to Evolution API"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                timeout=self.timeout
            )
            
            logger.info(f"Evolution API {method} {endpoint}: {response.status_code}")
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'data': response.json(),
                    'status_code': response.status_code
                }
            else:
                logger.error(f"Evolution API Error: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': response.text,
                    'status_code': response.status_code
                }
                
        except requests.RequestException as e:
            logger.error(f"Evolution API Request Exception: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'status_code': 0
            }
    
    def create_instance(self, instance_name: str, webhook_url: str = None) -> Dict:
        """Create a new WhatsApp instance"""
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
        return self._make_request('GET', f'instance/connect/{instance_name}')
    
    def get_instance_status(self, instance_name: str) -> Dict:
        """Get connection status of an instance"""
        return self._make_request('GET', f'instance/connectionState/{instance_name}')
    
    def send_text_message(self, instance_name: str, phone: str, message: str) -> Dict:
        """Send text message via WhatsApp"""
        data = {
            'number': phone,
            'text': message
        }
        
        return self._make_request('POST', f'message/sendText/{instance_name}', data)
    
    def send_media_message(self, instance_name: str, phone: str, media_url: str, caption: str = "") -> Dict:
        """Send media message via WhatsApp"""
        data = {
            'number': phone,
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
        return self._make_request('DELETE', f'instance/delete/{instance_name}')
    
    def logout_instance(self, instance_name: str) -> Dict:
        """Logout WhatsApp instance"""
        return self._make_request('DELETE', f'instance/logout/{instance_name}')

# Test the service
def test_evolution_api_service():
    """Test function to verify Evolution API service works"""
    service = EvolutionAPIService()
    
    # Test getting all instances
    result = service.get_all_instances()
    
    if result['success']:
        print("Evolution API Service is working!")
        print(f"Found {len(result['data'])} instances")
        return True
    else:
        print(f"Evolution API Service error: {result['error']}")
        return False