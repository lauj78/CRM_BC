# marketing_campaigns/services/inbox_service.py

import logging
from django.utils import timezone
from marketing_campaigns.models_inbox import Conversation, ConversationMessage
from marketing_campaigns.models import CampaignTarget
from whatsapp_messaging.models import WhatsAppInstance

logger = logging.getLogger(__name__)


class InboxService:
    """Service to handle WhatsApp inbox operations"""
    
# In marketing_campaigns/services/inbox_service.py - ADD these methods to the InboxService class

    @staticmethod
    def send_reply(
        conversation_id: int,
        message_text: str,
        sent_by_user,
        message_type: str = 'text',
        media_url: str = None
    ):
        """
        Send a reply message in a conversation
        """
        from whatsapp_messaging.services.evolution_api import EvolutionAPIService
        
        try:
            # Get conversation
            conversation = Conversation.objects.get(id=conversation_id)
            
            # Get WhatsApp instance
            instance = WhatsAppInstance.objects.get(id=conversation.whatsapp_instance_id)
            
            # Initialize Evolution API service
            evolution_service = EvolutionAPIService()
            
            # Send message based on type
            if message_type == 'text':
                result = evolution_service.send_text_message(
                    instance_name=instance.instance_name,
                    phone=conversation.customer_phone,
                    message=message_text
                )
            else:
                # For media messages (future enhancement)
                result = evolution_service.send_media_message(
                    instance_name=instance.instance_name,
                    phone=conversation.customer_phone,
                    media_url=media_url,
                    caption=message_text
                )
            
            # Handle API response
            if result['success']:
                # Create message record
                message = ConversationMessage.objects.create(
                    conversation=conversation,
                    direction='outbound',
                    message_type=message_type,
                    message_text=message_text,
                    media_url=media_url,
                    sent_by=sent_by_user,
                    evolution_message_id=result.get('data', {}).get('key', {}).get('id', ''),
                    delivery_status='sent',
                    sent_at=timezone.now()
                )
                
                # Update conversation
                conversation.last_message_at = timezone.now()
                conversation.last_agent_message_at = timezone.now()
                conversation.status = 'replied'
                conversation.total_messages += 1
                
                # Assign to user if not already assigned
                if not conversation.assigned_to:
                    conversation.assigned_to = sent_by_user
                
                conversation.save()
                
                logger.info(f"Sent reply message {message.id} in conversation {conversation_id}")
                
                return {
                    'success': True,
                    'message': message,
                    'api_response': result.get('data')
                }
            else:
                logger.error(f"Failed to send message: {result.get('error')}")
                return {
                    'success': False,
                    'error': result.get('error', 'Failed to send message')
                }
                
        except Conversation.DoesNotExist:
            logger.error(f"Conversation {conversation_id} not found")
            return {
                'success': False,
                'error': 'Conversation not found'
            }
        except WhatsAppInstance.DoesNotExist:
            logger.error(f"WhatsApp instance not found for conversation {conversation_id}")
            return {
                'success': False,
                'error': 'WhatsApp instance not found'
            }
        except Exception as e:
            logger.error(f"Error sending reply: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def get_conversation_list(tenant_id: int, status_filter=None, assigned_to=None):
        """
        Get list of conversations with filters
        """
        queryset = Conversation.objects.filter(tenant_id=tenant_id)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if assigned_to:
            queryset = queryset.filter(assigned_to=assigned_to)
        
        return queryset.select_related('assigned_to').prefetch_related('messages') 
    
   
    @staticmethod
    def process_inbound_message(
        tenant_id: int,
        whatsapp_instance_id: int,
        from_phone: str,
        message_text: str,
        message_type: str = 'text',
        media_url: str = None,
        evolution_message_id: str = None,
        whatsapp_message_id: str = None
    ):
        """
        Process an incoming WhatsApp message and create/update conversation
        """
        # Format phone number
        if not from_phone.startswith('+'):
            from_phone = f'+{from_phone}'
        
        logger.info(f"Processing inbound message from {from_phone} for tenant {tenant_id}")
        
        try:
            # Get WhatsApp instance details
            instance = WhatsAppInstance.objects.get(id=whatsapp_instance_id)
            
            # Find or create conversation
            conversation, created = Conversation.objects.get_or_create(
                tenant_id=tenant_id,
                customer_phone=from_phone,
                whatsapp_instance_id=whatsapp_instance_id,
                defaults={
                    'whatsapp_instance_name': instance.instance_name,
                    'status': 'unread',
                    'first_message_at': timezone.now(),
                    'last_message_at': timezone.now(),
                    'last_customer_message_at': timezone.now(),
                }
            )
            
            if created:
                logger.info(f"Created new conversation for {from_phone}")
                
                # Try to find customer name from recent campaign targets
                try:
                    from tenants.context import get_current_db
                    current_db = get_current_db()
                    
                    recent_target = CampaignTarget.objects.using(current_db).filter(                                      
                        phone_number=from_phone
                    ).order_by('-created_at').first()
                    
                    if recent_target:
                        if recent_target.member_data:
                            conversation.customer_name = recent_target.member_data.get('name', '')
                        conversation.originated_from_campaign = recent_target.campaign
                        conversation.save()
                except Exception as e:
                    logger.debug(f"Could not find campaign target: {e}")
            else:
                # Update existing conversation
                conversation.last_message_at = timezone.now()
                conversation.last_customer_message_at = timezone.now()
                
                # Reopen if was closed
                if conversation.status == 'closed':
                    conversation.status = 'open'
                # Mark as unread if was replied
                elif conversation.status == 'replied':
                    conversation.status = 'unread'
                
                conversation.unread_count += 1
                conversation.total_messages += 1
                conversation.save()
            
            # Create message record
            message = ConversationMessage.objects.create(
                conversation=conversation,
                direction='inbound',
                message_type=message_type,
                message_text=message_text,
                media_url=media_url,
                evolution_message_id=evolution_message_id,
                whatsapp_message_id=whatsapp_message_id,
                sent_at=timezone.now(),
                is_read=False
            )
            
            logger.info(f"Saved message {message.id} for conversation {conversation.id}")
            
            return conversation, message
            
        except WhatsAppInstance.DoesNotExist:
            logger.error(f"WhatsApp instance {whatsapp_instance_id} not found")
            raise
        except Exception as e:
            logger.error(f"Error processing inbound message: {str(e)}")
            raise
    
    @staticmethod
    def mark_messages_read(conversation_id: int, user=None):
        """Mark all unread messages in a conversation as read"""
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            
            # Mark messages as read
            unread_messages = conversation.messages.filter(
                direction='inbound',
                is_read=False
            )
            
            count = unread_messages.update(
                is_read=True,
                read_at=timezone.now()
            )
            
            # Update conversation unread count
            conversation.unread_count = 0
            if conversation.status == 'unread':
                conversation.status = 'open'
            conversation.save()
            
            logger.info(f"Marked {count} messages as read in conversation {conversation_id}")
            return count
            
        except Conversation.DoesNotExist:
            logger.error(f"Conversation {conversation_id} not found")
            return 0