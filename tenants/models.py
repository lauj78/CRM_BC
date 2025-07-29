# tenants/models.py
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta

def one_month_from_today():
    return timezone.now().date() + timedelta(days=30)

class Tenant(models.Model):
    tenant_id = models.CharField(max_length=100, unique=True, help_text="Unique identifier for the tenant")
    name = models.CharField(max_length=100, help_text="Name of the tenant/customer")
    db_alias = models.CharField(max_length=100, help_text="Database alias from settings")
    created_on = models.DateField(auto_now_add=True, help_text="Date the tenant was created")
    
    # Add subscription fields
    is_active = models.BooleanField(
        default=True,
        help_text="Enable/disable tenant access"
    )
    subscription_start = models.DateField(
        default=timezone.now,
        help_text="Subscription start date"
    )
    subscription_end = models.DateField(
        default=one_month_from_today, 
        help_text="Subscription expiration date"
    )
    contact_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Primary contact email"
    )
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Primary contact phone"
    )
    
    # Status properties
    @property
    def status(self):
        if not self.is_active:
            return "Suspended"
        if timezone.now().date() > self.subscription_end:
            return "Expired"
        return "Active"
    
    @property
    def days_remaining(self):
        return max(0, (self.subscription_end - timezone.now().date()).days)
    
    def __str__(self):
        return self.name
    
    def clean(self):
        # Validate subscription dates
        if self.subscription_start and self.subscription_end:
            if self.subscription_end < self.subscription_start:
                raise ValidationError("Subscription end date must be after start date")
    
    class Meta:
        ordering = ['-subscription_end']