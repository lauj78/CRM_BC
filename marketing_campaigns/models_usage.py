# marketing_campaigns/models_usage.py
from django.db import models
from django.utils import timezone
from datetime import timedelta

class WhatsAppInstanceUsage(models.Model):
    """Track WhatsApp instance usage for anti-ban rotation"""
    
    instance_name = models.CharField(
        max_length=100, 
        unique=True,
        db_index=True,
        help_text="WhatsApp instance identifier"
    )
    
    # Real-time tracking
    messages_sent_today = models.IntegerField(
        default=0,
        help_text="Messages sent today (resets at midnight)"
    )
    messages_sent_this_hour = models.IntegerField(
        default=0,
        help_text="Messages sent in current hour"
    )
    
    # Last activity
    last_message_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When last message was sent"
    )
    
    # Cooldown management
    is_in_cooldown = models.BooleanField(
        default=False,
        help_text="Is instance currently in cooldown"
    )
    cooldown_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When cooldown ends"
    )
    
    # Round-robin position
    last_used_position = models.IntegerField(
        default=0,
        help_text="Last position in round-robin rotation"
    )
    
    # Health tracking
    consecutive_failures = models.IntegerField(
        default=0,
        help_text="Consecutive send failures"
    )
    total_messages_sent = models.IntegerField(
        default=0,
        help_text="Total lifetime messages"
    )
    total_failures = models.IntegerField(
        default=0,
        help_text="Total lifetime failures"
    )
    
    # Automatic resets
    last_hourly_reset = models.DateTimeField(
        default=timezone.now,
        help_text="When hourly counter was reset"
    )
    last_daily_reset = models.DateTimeField(
        default=timezone.now,
        help_text="When daily counter was reset"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'marketing_whatsapp_instance_usage'
        verbose_name = 'WhatsApp Instance Usage'
        verbose_name_plural = 'WhatsApp Instance Usage'
    
    def __str__(self):
        return f"{self.instance_name} (Today: {self.messages_sent_today})"
    
    def reset_hourly_counter(self):
        """Reset hourly message counter"""
        self.messages_sent_this_hour = 0
        self.last_hourly_reset = timezone.now()
        self.save(update_fields=['messages_sent_this_hour', 'last_hourly_reset'])
    
    def reset_daily_counter(self):
        """Reset daily message counter"""
        self.messages_sent_today = 0
        self.last_daily_reset = timezone.now()
        self.save(update_fields=['messages_sent_today', 'last_daily_reset'])
    
    def check_and_reset_counters(self):
        """Check if counters need reset based on time"""
        now = timezone.now()
        
        # Check hourly reset
        if (now - self.last_hourly_reset).total_seconds() >= 3600:
            self.reset_hourly_counter()
        
        # Check daily reset
        if now.date() > self.last_daily_reset.date():
            self.reset_daily_counter()
    
    def is_available(self):
        """Check if instance is available to send"""
        now = timezone.now()
        
        # Check cooldown
        if self.is_in_cooldown and self.cooldown_until:
            if now < self.cooldown_until:
                return False
            else:
                # Cooldown expired, clear it
                self.is_in_cooldown = False
                self.cooldown_until = None
                self.save(update_fields=['is_in_cooldown', 'cooldown_until'])
        
        return True
    
    def record_message_sent(self, success=True):
        """Record a message send attempt"""
        self.check_and_reset_counters()
        
        self.messages_sent_this_hour += 1
        self.messages_sent_today += 1
        self.total_messages_sent += 1
        self.last_message_sent_at = timezone.now()
        
        if success:
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
            self.total_failures += 1
        
        self.save()
    
    def enter_cooldown(self, minutes=15):
        """Put instance in cooldown"""
        self.is_in_cooldown = True
        self.cooldown_until = timezone.now() + timedelta(minutes=minutes)
        self.save(update_fields=['is_in_cooldown', 'cooldown_until'])
    
    @property
    def success_rate(self):
        """Calculate lifetime success rate"""
        if self.total_messages_sent == 0:
            return 100.0
        successful = self.total_messages_sent - self.total_failures
        return round((successful / self.total_messages_sent) * 100, 1)