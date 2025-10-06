# marketing_campaigns/models_inbox.py
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class Conversation(models.Model):
    """Track WhatsApp conversations with customers"""
    
    STATUS_CHOICES = [
        ('unread', 'Unread'),
        ('open', 'Open'),
        ('replied', 'Replied'),
        ('closed', 'Closed'),
    ]
    
    # Tenant isolation
    tenant_id = models.IntegerField(db_index=True)
    
    # Customer info
    customer_phone = models.CharField(max_length=20, db_index=True)
    customer_name = models.CharField(max_length=200, blank=True)
    
    # WhatsApp instance handling this conversation
    whatsapp_instance_id = models.IntegerField()
    whatsapp_instance_name = models.CharField(max_length=100)
    
    # Link to campaign if customer replied to campaign message
    originated_from_campaign = models.ForeignKey(
        'Campaign',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations'
    )
    
    # Conversation management
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unread')
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_conversations'
    )
    
    # Message counts
    unread_count = models.IntegerField(default=0)
    total_messages = models.IntegerField(default=0)
    
    # Timestamps
    first_message_at = models.DateTimeField(default=timezone.now)
    last_message_at = models.DateTimeField(default=timezone.now)
    last_customer_message_at = models.DateTimeField(null=True, blank=True)
    last_agent_message_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'marketing_conversations'
        ordering = ['-last_message_at']
        indexes = [
            models.Index(fields=['tenant_id', 'customer_phone']),
            models.Index(fields=['tenant_id', 'status', '-last_message_at']),
            models.Index(fields=['tenant_id', 'assigned_to']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'customer_phone', 'whatsapp_instance_id'],
                name='unique_conversation_per_instance'
            )
        ]
    
    def __str__(self):
        return f"{self.customer_name or self.customer_phone} - {self.status}"


class ConversationMessage(models.Model):
    """Individual messages in conversations"""
    
    DIRECTION_CHOICES = [
        ('inbound', 'Customer to Us'),
        ('outbound', 'Us to Customer'),
    ]
    
    MESSAGE_TYPE_CHOICES = [
        ('text', 'Text'),
        ('image', 'Image'), 
        ('document', 'Document'),
        ('audio', 'Audio'),
        ('video', 'Video'),
    ]
    
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    
    # Message details
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPE_CHOICES, default='text')
    message_text = models.TextField()
    media_url = models.URLField(blank=True, null=True)
    
    # For outbound messages - who sent it
    sent_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_inbox_messages'
    )
    
    # Evolution API tracking
    evolution_message_id = models.CharField(max_length=200, blank=True)
    whatsapp_message_id = models.CharField(max_length=200, blank=True)
    
    # Status tracking
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    delivery_status = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('sending', 'Sending'),
            ('sent', 'Sent'),
            ('delivered', 'Delivered'),
            ('read', 'Read'),
            ('failed', 'Failed'),
        ]
    )
    
    sent_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'marketing_conversation_messages'
        ordering = ['sent_at']
        indexes = [
            models.Index(fields=['conversation', 'sent_at']),
            models.Index(fields=['direction', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.direction} - {self.message_text[:50]}"