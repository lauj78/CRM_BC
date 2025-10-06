# marketing_campaigns/views_inbox.py
import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages as django_messages
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.db.models import Q

from .models_inbox import Conversation, ConversationMessage
from .services.inbox_service import InboxService

logger = logging.getLogger(__name__)


@login_required
def inbox_list(request, tenant_id):
    """Display list of all conversations"""
    if not request.tenant:
        django_messages.error(request, "Tenant not found.")
        return redirect('account_locked')
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    
    # Get conversations
    conversations = Conversation.objects.filter(tenant_id=request.tenant.id)
    
    # Apply filters
    if status_filter:
        conversations = conversations.filter(status=status_filter)
    
    if search_query:
        conversations = conversations.filter(
            Q(customer_phone__icontains=search_query) |
            Q(customer_name__icontains=search_query)
        )
    
    # Order by last message
    conversations = conversations.order_by('-last_message_at')
    
    # Get status counts for sidebar
    status_counts = {
        'all': Conversation.objects.filter(tenant_id=request.tenant.id).count(),
        'unread': Conversation.objects.filter(tenant_id=request.tenant.id, status='unread').count(),
        'open': Conversation.objects.filter(tenant_id=request.tenant.id, status='open').count(),
        'replied': Conversation.objects.filter(tenant_id=request.tenant.id, status='replied').count(),
        'closed': Conversation.objects.filter(tenant_id=request.tenant.id, status='closed').count(),
    }
    
    context = {
        'conversations': conversations,
        'status_filter': status_filter,
        'search_query': search_query,
        'status_counts': status_counts,
        'tenant_id': request.tenant.tenant_id,
    }
    
    return render(request, 'marketing_campaigns/inbox/inbox_list.html', context)


@login_required
def conversation_detail(request, tenant_id, conversation_id):
    """Display conversation messages and reply form"""
    if not request.tenant:
        django_messages.error(request, "Tenant not found.")
        return redirect('account_locked')
    
    # Get conversation
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        tenant_id=request.tenant.id
    )
    
    # Mark messages as read
    InboxService.mark_messages_read(conversation_id, user=request.user)
    
    # Get messages
    messages = conversation.messages.all().order_by('sent_at')
    
    # Handle reply submission
    if request.method == 'POST':
        message_text = request.POST.get('message_text', '').strip()
        
        if message_text:
            result = InboxService.send_reply(
                conversation_id=conversation_id,
                message_text=message_text,
                sent_by_user=request.user
            )
            
            if result['success']:
                django_messages.success(request, "Message sent successfully!")
                return redirect('marketing_campaigns:conversation_detail', 
                               tenant_id=request.tenant.tenant_id, 
                               conversation_id=conversation_id)
            else:
                django_messages.error(request, f"Failed to send message: {result.get('error')}")
        else:
            django_messages.error(request, "Message cannot be empty")
    
    context = {
        'conversation': conversation,
        'messages': messages,
        'tenant_id': request.tenant.tenant_id,
    }
    
    return render(request, 'marketing_campaigns/inbox/conversation_detail.html', context)


@login_required
@require_http_methods(["POST"])
def send_reply_ajax(request, tenant_id, conversation_id):
    """Send reply via AJAX"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Tenant not found'})
    
    try:
        data = json.loads(request.body)
        message_text = data.get('message_text', '').strip()
        
        if not message_text:
            return JsonResponse({'success': False, 'error': 'Message cannot be empty'})
        
        result = InboxService.send_reply(
            conversation_id=conversation_id,
            message_text=message_text,
            sent_by_user=request.user
        )
        
        if result['success']:
            message = result['message']
            return JsonResponse({
                'success': True,
                'message': {
                    'id': message.id,
                    'text': message.message_text,
                    'sent_at': message.sent_at.strftime('%Y-%m-%d %H:%M'),
                    'sent_by': request.user.username
                }
            })
        else:
            return JsonResponse(result)
            
    except Exception as e:
        logger.error(f"Error sending reply: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def update_conversation_status(request, tenant_id, conversation_id):
    """Update conversation status"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Tenant not found'})
    
    try:
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            tenant_id=request.tenant.id
        )
        
        data = json.loads(request.body)
        new_status = data.get('status')
        
        if new_status in ['unread', 'open', 'replied', 'closed']:
            conversation.status = new_status
            conversation.save()
            
            return JsonResponse({
                'success': True,
                'status': conversation.status
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid status'
            })
            
    except Exception as e:
        logger.error(f"Error updating conversation status: {e}")
        return JsonResponse({'success': False, 'error': str(e)})
    

@login_required
@require_http_methods(["POST"])
def delete_conversation(request, tenant_id, conversation_id):
    """Delete a conversation"""
    if not request.tenant:
        django_messages.error(request, "Tenant not found.")
        return redirect('account_locked')
    
    try:
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            tenant_id=request.tenant.id
        )
        
        conversation_phone = conversation.customer_phone
        conversation.delete()
        
        django_messages.success(request, f"Conversation with {conversation_phone} deleted successfully")
        return redirect('marketing_campaigns:inbox_list', tenant_id=request.tenant.tenant_id)
        
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        django_messages.error(request, f"Failed to delete conversation: {str(e)}")
        return redirect('marketing_campaigns:inbox_list', tenant_id=request.tenant.tenant_id)