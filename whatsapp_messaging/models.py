# whatsapp_messaging/models.py

from django.db import models
from django.utils import timezone
from tenants.models import Tenant # This import is still useful for reference but no longer for the ForeignKey

class WhatsAppInstance(models.Model):
    """WhatsApp instance linked to a tenant and an external API."""
    
    # Instance identification
    # We are replacing the ForeignKey with a simple IntegerField
    # to avoid the cross-database foreign key constraint.
    tenant_id = models.IntegerField(
        db_index=True,
        help_text="The ID of the tenant this WhatsApp instance belongs to."
    )
    instance_name = models.CharField(
        max_length=100,
        help_text="Unique name for this WhatsApp instance within the tenant."
    )
    external_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Unique ID from the external WhatsApp API (e.g., Evolution API)."
    )
    api_key = models.CharField(
        max_length=255,
        default='', 
        help_text="The API key or access token for this instance."
    )

    # Phone number information
    phone_number = models.CharField(
        max_length=20,
        help_text="WhatsApp business phone number."
    )
    owner_jid = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="WhatsApp JID from the external API."
    )
    
    # Connection status
    class ConnectionStatus(models.TextChoices):
        DISCONNECTED = 'disconnected', 'Disconnected'
        CONNECTING = 'connecting', 'Connecting'
        CONNECTED = 'connected', 'Connected'
        CLOSED = 'closed', 'Closed'

    status = models.CharField(
        max_length=20,
        choices=ConnectionStatus.choices,
        default=ConnectionStatus.DISCONNECTED
    )
    
    # API integration data
    qr_code = models.TextField(
        blank=True,
        null=True,
        help_text="Base64 QR code for authentication."
    )
    session_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Session information from the external API."
    )
    
    # Rate limiting
    daily_message_limit = models.PositiveIntegerField(
        default=1000,
        help_text="Daily message sending limit."
    )
    daily_message_count = models.PositiveIntegerField(
        default=0,
        help_text="Messages sent today."
    )
    last_message_sent = models.DateTimeField(null=True, blank=True)
    
    # Instance settings
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the last successful sync with the external API."
    )
    
    # Profile information
    profile_name = models.CharField(max_length=100, blank=True, null=True)
    profile_picture_url = models.URLField(blank=True, null=True)
    
    class Meta:
        db_table = 'whatsapp_instances'
        ordering = ['-created_at']
        # IMPORTANT: Updated the unique_together constraint to use 'tenant_id'.
        unique_together = ('tenant_id', 'instance_name')
    
    def __str__(self):
        return f"{self.instance_name} ({self.phone_number})"
    
    @property
    def is_connected(self):
        return self.status == self.ConnectionStatus.CONNECTED
    
    def reset_daily_count(self):
        """Reset daily message count (called by a scheduler)."""
        self.daily_message_count = 0
        self.save()

class MessageQueue(models.Model):
    """Queue for WhatsApp messages to be sent."""
    
    # Message identification
    whatsapp_instance = models.ForeignKey(
        WhatsAppInstance,
        on_delete=models.CASCADE,
        related_name='queued_messages',
        help_text="The WhatsApp instance to send this message from."
    )
    
    # Recipient information
    recipient_phone = models.CharField(
        max_length=20,
        help_text="Recipient phone number."
    )
    recipient_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Recipient display name."
    )
    
    # Message content
    class MessageType(models.TextChoices):
        TEXT = 'text', 'Text'
        IMAGE = 'image', 'Image'
        DOCUMENT = 'document', 'Document'

    message_content = models.TextField(
        blank=True,
        help_text="Message text content."
    )
    message_type = models.CharField(
        max_length=20,
        choices=MessageType.choices,
        default=MessageType.TEXT
    )
    media_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL for media messages."
    )
    
    # Scheduling
    scheduled_at = models.DateTimeField(
        default=timezone.now,
        help_text="When to send this message."
    )
    priority = models.IntegerField(
        default=5,
        help_text="Message priority (1=high, 10=low)."
    )
    
    # Status tracking
    class MessageStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENDING = 'sending', 'Sending'
        SENT = 'sent', 'Sent'
        DELIVERED = 'delivered', 'Delivered'
        READ = 'read', 'Read'
        FAILED = 'failed', 'Failed'

    status = models.CharField(
        max_length=20,
        choices=MessageStatus.choices,
        default=MessageStatus.PENDING
    )
    
    # Retry logic
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)
    
    # API response
    evolution_message_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Message ID from Evolution API."
    )
    api_response = models.JSONField(
        default=dict,
        blank=True,
        help_text="Full API response."
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text="Error details if failed."
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'message_queue'
        ordering = ['priority', 'scheduled_at']
        indexes = [
            models.Index(fields=['status', 'scheduled_at']),
            models.Index(fields=['whatsapp_instance', 'status']),
        ]
    
    def __str__(self):
        return f"Message to {self.recipient_phone} via {self.whatsapp_instance.instance_name}"
    
    @property
    def can_retry(self):
        return self.retry_count < self.max_retries and self.status == self.MessageStatus.FAILED

class WebhookEvent(models.Model):
    """Store webhook events from Evolution API."""
    
    # Event identification
    whatsapp_instance = models.ForeignKey(
        WhatsAppInstance,
        on_delete=models.SET_NULL, # Set to null if the instance is deleted
        null=True,
        blank=True,
        help_text="The WhatsApp instance this event is related to."
    )
    event_type = models.CharField(
        max_length=50,
        help_text="Type of webhook event."
    )
    
    # Evolution API data
    evolution_message_id = models.CharField(max_length=255, blank=True, null=True)
    whatsapp_message_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Webhook payload
    payload = models.JSONField(
        default=dict,
        help_text="Raw webhook data from Evolution API."
    )
    
    # Processing status
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_error = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'webhook_events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['processed', 'created_at']),
            models.Index(fields=['whatsapp_instance', 'event_type']),
        ]
    
    def __str__(self):
        instance_name = self.whatsapp_instance.instance_name if self.whatsapp_instance else 'N/A'
        return f"{self.event_type} from {instance_name}"
