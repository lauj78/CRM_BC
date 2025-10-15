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
from django.core.paginator import Paginator

from .models_inbox import Conversation, ConversationMessage
from .services.inbox_service import InboxService

logger = logging.getLogger(__name__)


@login_required
def inbox_list(request, tenant_id):
    """
    Display list of all conversations with TWO SECTIONS:
    1. Campaign Conversations (from marketing campaigns)
    2. Regular Chats (direct messages)
    """
    if not request.tenant:
        django_messages.error(request, "Tenant not found.")
        return redirect('account_locked')
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    
    # Base query
    all_conversations = Conversation.objects.filter(tenant_id=request.tenant.id)
    
    # Apply search filter
    if search_query:
        all_conversations = all_conversations.filter(
            Q(customer_phone__icontains=search_query) |
            Q(customer_name__icontains=search_query)
        )
    
    # Apply status filter
    if status_filter:
        all_conversations = all_conversations.filter(status=status_filter)
    
    # ====== SEPARATE INTO TWO SECTIONS ======
    
    # Section 1: Campaign Conversations (has originated_from_campaign)
    campaign_conversations = all_conversations.filter(
        originated_from_campaign__isnull=False
    ).select_related(
        'originated_from_campaign',
        'assigned_to'
    ).order_by('-last_message_at')
    
    # Section 2: Regular Chats (no campaign origin)
    regular_conversations = all_conversations.filter(
        originated_from_campaign__isnull=True
    ).select_related(
        'assigned_to'
    ).order_by('-last_message_at')
    
    # ====== PAGINATION FOR CAMPAIGN SECTION ======
    campaign_page = request.GET.get('campaign_page', 1)
    campaign_paginator = Paginator(campaign_conversations, 10)  # 10 per page
    campaign_page_obj = campaign_paginator.get_page(campaign_page)
    
    # Add unread count and last message preview for campaign conversations
    for conversation in campaign_page_obj:
        conversation.unread_count = ConversationMessage.objects.filter(
            conversation=conversation,
            direction='inbound',
            is_read=False
        ).count()
        
        last_message = ConversationMessage.objects.filter(
            conversation=conversation
        ).order_by('-sent_at').first()
        conversation.last_message_preview = last_message.message_text[:50] if last_message else ""
    
    # ====== PAGINATION FOR REGULAR SECTION ======
    regular_page = request.GET.get('regular_page', 1)
    regular_paginator = Paginator(regular_conversations, 10)  # 10 per page
    regular_page_obj = regular_paginator.get_page(regular_page)
    
    # Add unread count and last message preview for regular conversations
    for conversation in regular_page_obj:
        conversation.unread_count = ConversationMessage.objects.filter(
            conversation=conversation,
            direction='inbound',
            is_read=False
        ).count()
        
        last_message = ConversationMessage.objects.filter(
            conversation=conversation
        ).order_by('-sent_at').first()
        conversation.last_message_preview = last_message.message_text[:50] if last_message else ""
    
    # ====== STATUS COUNTS (for filter sidebar) ======
    status_counts = {
        'all': Conversation.objects.filter(tenant_id=request.tenant.id).count(),
        'unread': Conversation.objects.filter(tenant_id=request.tenant.id, status='unread').count(),
        'open': Conversation.objects.filter(tenant_id=request.tenant.id, status='open').count(),
        'replied': Conversation.objects.filter(tenant_id=request.tenant.id, status='replied').count(),
        'closed': Conversation.objects.filter(tenant_id=request.tenant.id, status='closed').count(),
    }
    
    # Count totals for each section
    campaign_total = campaign_conversations.count()
    regular_total = regular_conversations.count()
    
    context = {
        # Two sections with pagination
        'campaign_conversations': campaign_page_obj,
        'regular_conversations': regular_page_obj,
        'campaign_total': campaign_total,
        'regular_total': regular_total,
        
        # Existing features
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
    conversation_messages = conversation.messages.all().order_by('sent_at')
    
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
        'conversation_messages': conversation_messages,
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