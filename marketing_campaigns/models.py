# marketing_campaigns/models.py
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from decimal import Decimal
import json
import re
import random

# ================================
# TENANT SETTINGS & CONFIGURATION
# ================================

class TenantCampaignSettings(models.Model):
    """Tenant-specific campaign configuration and anti-ban settings"""
    
    # Anti-ban settings (tenant configurable)
    default_rate_limit_per_hour = models.IntegerField(
        default=20, 
        help_text="Messages per hour per instance"
    )
    default_min_delay_minutes = models.IntegerField(
        default=1, 
        help_text="Minimum delay between messages"
    )
    default_max_delay_minutes = models.IntegerField(
        default=5, 
        help_text="Maximum delay between messages"
    )
    default_messages_per_instance = models.IntegerField(
        default=50, 
        help_text="Messages before switching instance"
    )
    
    # WhatsApp instances available to this tenant
    whatsapp_instances = models.JSONField(
        default=list,
        help_text="List of WhatsApp instance IDs: ['instance1', 'instance2']"
    )
    
    # Custom variables this tenant uses
    custom_variables = models.JSONField(
        default=dict,
        help_text='Custom template variables: {"bonus": {"type": "currency", "description": "Bonus amount"}}'
    )
    
    # Phone number validation settings
    primary_country_code = models.CharField(
        max_length=5, 
        default='ID', 
        help_text="Primary country code (ID, MY, TH, etc.)"
    )
    supported_countries = models.JSONField(
        default=list,
        help_text="Supported country codes: ['ID', 'MY', 'TH', 'SG']"
    )
    
    # Failed number handling policy
    max_retry_attempts = models.IntegerField(
        default=3, 
        help_text="Max attempts before flagging number"
    )
    auto_exclude_failed_numbers = models.BooleanField(
        default=False, 
        help_text="Auto-exclude flagged numbers by default"
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'marketing_tenant_settings'
        verbose_name = 'Tenant Campaign Settings'
        verbose_name_plural = 'Tenant Campaign Settings'
    
    def __str__(self):
        return f"Campaign Settings ({self.primary_country_code})"
    
    def get_default_variables(self):
        """Get standard + custom variables available"""
        standard = {
            "phone_number": {"type": "text", "description": "Phone number"},
            "name": {"type": "text", "description": "Member name"},
        }
        return {**standard, **self.custom_variables}
    
    @classmethod
    def get_instance(cls):
        """Get or create the singleton settings instance"""
        settings, created = cls.objects.get_or_create(
            id=1,
            defaults={
                'primary_country_code': 'ID',
                'supported_countries': ['ID', 'MY', 'TH', 'SG', 'PH'],
                'custom_variables': {
                    'bonus': {'type': 'currency', 'description': 'Bonus amount'},
                    'coupon_code': {'type': 'text', 'description': 'Promotional code'}
                }
            }
        )
        return settings

# ================================
# PHONE NUMBER MANAGEMENT
# ================================

class PhoneNumberHistory(models.Model):
    """Track phone number WhatsApp availability and performance"""
    
    WHATSAPP_STATUS_CHOICES = [
        ('unknown', 'Unknown'),
        ('confirmed', 'Has WhatsApp'),
        ('not_available', 'No WhatsApp'),
        ('blocked', 'Blocked/Banned'),
        ('invalid', 'Invalid Number'),
    ]
    
    RISK_LEVEL_CHOICES = [
        ('low', 'Low Risk'), 
        ('medium', 'Medium Risk'), 
        ('high', 'High Risk')
    ]
    
    phone_number = models.CharField(max_length=20, unique=True, db_index=True)
    whatsapp_status = models.CharField(
        max_length=20, 
        choices=WHATSAPP_STATUS_CHOICES, 
        default='unknown'
    )
    country_code = models.CharField(max_length=5, blank=True)
    
    # Performance tracking
    total_attempts = models.IntegerField(default=0)
    successful_sends = models.IntegerField(default=0)
    failed_sends = models.IntegerField(default=0)
    last_success_date = models.DateTimeField(null=True, blank=True)
    last_failure_date = models.DateTimeField(null=True, blank=True)
    
    # Failure analysis
    failure_reasons = models.JSONField(
        default=list,
        help_text="List of failure reasons: ['not_on_whatsapp', 'blocked', 'invalid_number']"
    )
    
    # Risk assessment
    risk_level = models.CharField(
        max_length=10,
        choices=RISK_LEVEL_CHOICES,
        default='low'
    )
    
    # Admin flags
    is_flagged = models.BooleanField(
        default=False, 
        help_text="Flagged for admin review"
    )
    admin_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'marketing_phone_history'
        verbose_name = 'Phone Number History'
        verbose_name_plural = 'Phone Number Histories'
        indexes = [
            models.Index(fields=['whatsapp_status', 'risk_level']),
            models.Index(fields=['is_flagged']),
            models.Index(fields=['phone_number']),
        ]
    
    def __str__(self):
        return f"{self.phone_number} ({self.whatsapp_status})"
    
    @property
    def success_rate(self):
        """Calculate success rate percentage"""
        if self.total_attempts == 0:
            return 0
        return round((self.successful_sends / self.total_attempts) * 100, 1)
    
    def update_from_campaign_result(self, success, failure_reason=None):
        """Update history from campaign result"""
        self.total_attempts += 1
        
        if success:
            self.successful_sends += 1
            self.last_success_date = timezone.now()
            if self.whatsapp_status == 'unknown':
                self.whatsapp_status = 'confirmed'
        else:
            self.failed_sends += 1
            self.last_failure_date = timezone.now()
            
            if failure_reason:
                if failure_reason not in self.failure_reasons:
                    self.failure_reasons.append(failure_reason)
            
            # Update status based on failure pattern
            if 'not_on_whatsapp' in self.failure_reasons and self.failed_sends >= 2:
                self.whatsapp_status = 'not_available'
            elif 'blocked' in self.failure_reasons:
                self.whatsapp_status = 'blocked'
            elif 'invalid_number' in self.failure_reasons:
                self.whatsapp_status = 'invalid'
        
        # Update risk level
        self._calculate_risk_level()
        
        # Flag for review if high risk
        if self.risk_level == 'high' and not self.is_flagged:
            self.is_flagged = True
        
        self.save()
    
    def _calculate_risk_level(self):
        """Calculate risk level based on performance"""
        if self.total_attempts < 3:
            self.risk_level = 'low'
        elif self.success_rate >= 70:
            self.risk_level = 'low'
        elif self.success_rate >= 30:
            self.risk_level = 'medium'
        else:
            self.risk_level = 'high'

# ================================
# CATEGORIES & TEMPLATES
# ================================

class CampaignCategory(models.Model):
    """User-defined campaign categories"""
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(
        max_length=7, 
        default='#007bff', 
        help_text="Hex color for UI (e.g., #ff6b6b)"
    )
    icon = models.CharField(
        max_length=50, 
        blank=True, 
        help_text="Icon name for UI (e.g., 'star', 'gift')"
    )
    
    # System vs user created
    is_system_default = models.BooleanField(default=False)
    created_by = models.CharField(max_length=100, blank=True)
    
    # Usage tracking
    campaign_count = models.IntegerField(default=0)
    template_count = models.IntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'marketing_campaign_categories'
        verbose_name = 'Campaign Category'
        verbose_name_plural = 'Campaign Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def update_counts(self):
        """Update usage statistics"""
        self.campaign_count = self.campaign_set.count()
        self.template_count = self.messagetemplate_set.count()
        self.save(update_fields=['campaign_count', 'template_count'])

class MessageTemplate(models.Model):
    """Message templates with flexible variable system"""
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(CampaignCategory, on_delete=models.CASCADE)
    
    # Template content
    content = models.TextField(
        help_text="Use {{variable_name}} for dynamic content"
    )
    
    # Anti-ban variations
    variation_a = models.TextField(blank=True, help_text="Alternative version A")
    variation_b = models.TextField(blank=True, help_text="Alternative version B")  
    use_variations = models.BooleanField(
        default=False, 
        help_text="Randomly use variations for anti-ban"
    )
    
    # Variable system
    variables_used = models.JSONField(
        default=list,
        help_text="Variables detected in content: ['name', 'bonus', 'coupon_code']"
    )
    
    # Template metadata
    is_system_template = models.BooleanField(default=False)
    created_by = models.CharField(max_length=100, blank=True)
    
    # Performance tracking
    usage_count = models.IntegerField(default=0)
    average_success_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0
    )
    last_used = models.DateTimeField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'marketing_message_templates'
        verbose_name = 'Message Template'
        verbose_name_plural = 'Message Templates'
        ordering = ['-usage_count', 'name']
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['is_system_template']),
        ]
    
    def __str__(self):
        icon = "🔧" if self.is_system_template else "👤"
        return f"{icon} {self.name}"
    
    def save(self, *args, **kwargs):
        # Auto-extract variables from content
        self.variables_used = self.extract_variables()
        super().save(*args, **kwargs)
        
        # Update category count
        if self.category_id:
            self.category.update_counts()
    
    def extract_variables(self):
        """Extract {{variable}} patterns from content and variations"""
        content_parts = [self.content]
        if self.variation_a:
            content_parts.append(self.variation_a)
        if self.variation_b:
            content_parts.append(self.variation_b)
        
        variables = set()
        for content in content_parts:
            variables.update(re.findall(r'\{\{(\w+)\}\}', content))
        
        return sorted(list(variables))
    
    def get_content_variation(self):
        """Get random variation for anti-ban"""
        if not self.use_variations:
            return self.content
        
        variations = [self.content]
        if self.variation_a:
            variations.append(self.variation_a)
        if self.variation_b:
            variations.append(self.variation_b)
        
        return random.choice(variations)
    
    def render_message(self, member_data):
        """Render template with member data"""
        content = self.get_content_variation()
        
        # Replace variables
        for variable in self.variables_used:
            placeholder = f"{{{{{variable}}}}}"
            value = member_data.get(variable, f"[{variable}]")  # Default if missing
            content = content.replace(placeholder, str(value))
        
        return content
    
    def increment_usage(self, success_rate=None):
        """Update usage statistics"""
        self.usage_count += 1
        self.last_used = timezone.now()
        
        if success_rate is not None:
            # Update average success rate (simple moving average)
            if self.usage_count == 1:
                self.average_success_rate = success_rate
            else:
                current_avg = float(self.average_success_rate)
                new_avg = ((current_avg * (self.usage_count - 1)) + success_rate) / self.usage_count
                self.average_success_rate = round(new_avg, 2)
        
        self.save(update_fields=['usage_count', 'last_used', 'average_success_rate'])

# ================================
# AUDIENCE MANAGEMENT
# ================================

class CustomAudience(models.Model):
    """Phone number audiences from uploads or targeting reports"""
    
    UPLOAD_METHOD_CHOICES = [
        ('csv_file', 'CSV File Upload'),
        ('textbox', 'Textbox Input'),
        ('targeting_report', 'Targeting Report'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    upload_method = models.CharField(max_length=20, choices=UPLOAD_METHOD_CHOICES)
    
    # Raw upload data
    raw_data = models.TextField(
        blank=True, 
        help_text="Original CSV data or textbox input"
    )
    
    # Processed phone numbers and data
    members = models.JSONField(
        default=list,
        help_text='List of members: [{"phone_number": "+628123456789", "name": "Ahmad", "bonus": "50000"}]'
    )
    
    # Statistics
    total_numbers = models.IntegerField(default=0)
    valid_numbers = models.IntegerField(default=0)
    invalid_numbers = models.IntegerField(default=0)
    flagged_numbers = models.IntegerField(default=0)
    
    # Processing results
    processing_errors = models.JSONField(
        default=list,
        help_text="Processing errors: ['Invalid phone: +123', 'Duplicate: +456']"
    )
    
    created_by = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'marketing_custom_audiences'
        verbose_name = 'Custom Audience'
        verbose_name_plural = 'Custom Audiences'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.total_numbers} numbers)"
    
    def process_csv_data(self, csv_data, country_codes=None):
        """Process CSV data and validate phone numbers"""
        import csv
        from io import StringIO
        
        if country_codes is None:
            settings = TenantCampaignSettings.get_instance()
            country_codes = settings.supported_countries or ['ID']
        
        self.raw_data = csv_data
        self.processing_errors = []
        processed_members = []
        
        try:
            # Parse CSV
            reader = csv.DictReader(StringIO(csv_data))
            
            # Check for required phone_number column
            if 'phone_number' not in reader.fieldnames:
                self.processing_errors.append("Missing required 'phone_number' column")
                self.save()
                return
            
            seen_phones = set()
            
            for row_num, row in enumerate(reader, 1):
                phone = row.get('phone_number', '').strip()
                if not phone:
                    continue
                
                # Check for duplicates
                if phone in seen_phones:
                    self.processing_errors.append(f"Row {row_num}: Duplicate phone number: {phone}")
                    continue
                
                seen_phones.add(phone)
                
                # Validate phone number
                is_valid, formatted_phone, country = self.validate_phone_number(phone, country_codes)
                
                if is_valid:
                    member_data = {
                        'phone_number': formatted_phone,
                        'country_code': country
                    }
                    
                    # Add other columns as custom data
                    for key, value in row.items():
                        if key != 'phone_number' and value:
                            member_data[key] = value.strip()
                    
                    processed_members.append(member_data)
                else:
                    self.processing_errors.append(f"Row {row_num}: Invalid phone number: {phone}")
        
        except Exception as e:
            self.processing_errors.append(f"CSV parsing error: {str(e)}")
        
        # Update statistics
        self.members = processed_members
        self.total_numbers = len(processed_members)
        self.valid_numbers = len(processed_members)
        self.invalid_numbers = len(self.processing_errors)
        
        # Check for flagged numbers
        self._check_flagged_numbers()
        
        self.save()

    def validate_phone_number(self, phone, country_codes):
        """Basic phone number validation - accepts any valid international format"""
        
        # Remove common formatting
        clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
        
        # Must start with + and contain only digits after (8-15 digits total)
        if not re.match(r'^\+\d{8,15}$', clean_phone):
            return False, phone, None
        
        # Try to detect country for informational purposes (but don't reject if unknown)
        detected_country = None
        
        # Country detection (for information only)
        country_mapping = {
            'ID': '+62',  # Indonesia
            'MY': '+60',  # Malaysia  
            'TH': '+66',  # Thailand
            'SG': '+65',  # Singapore
            'PH': '+63',  # Philippines
            'KH': '+855', # Cambodia
            'VN': '+84',  # Vietnam
            'LA': '+856', # Laos
            'MM': '+95',  # Myanmar
            'BN': '+673', # Brunei
        }
        
        # Try to detect country from phone prefix
        for country_code, prefix in country_mapping.items():
            if clean_phone.startswith(prefix):
                detected_country = country_code
                break
        
        # If no country detected, try some common patterns
        if not detected_country:
            if clean_phone.startswith('+1'):
                detected_country = 'US'
            elif clean_phone.startswith('+44'):
                detected_country = 'UK'
            elif clean_phone.startswith('+86'):
                detected_country = 'CN'
            elif clean_phone.startswith('+91'):
                detected_country = 'IN'
            # Add more as needed, or leave as 'UNKNOWN'
        
        # ALWAYS RETURN TRUE for valid format - don't reject based on country
        return True, clean_phone, detected_country or 'UNKNOWN'



    
    
    def _check_flagged_numbers(self):
        """Check which numbers are flagged in history"""
        flagged_count = 0
        
        for member in self.members:
            phone = member['phone_number']
            try:
                history = PhoneNumberHistory.objects.get(phone_number=phone)
                if history.is_flagged or history.risk_level == 'high':
                    member['is_flagged'] = True
                    member['risk_level'] = history.risk_level
                    member['whatsapp_status'] = history.whatsapp_status
                    member['success_rate'] = history.success_rate
                    flagged_count += 1
                else:
                    member['is_flagged'] = False
            except PhoneNumberHistory.DoesNotExist:
                member['is_flagged'] = False
        
        self.flagged_numbers = flagged_count
    
    def get_flagged_numbers_summary(self):
        """Get summary of flagged numbers for user review"""
        return [
            member for member in self.members 
            if member.get('is_flagged', False)
        ]

# ================================
# PRE-DEFINED TARGETING REPORTS
# ================================

class TargetingReport(models.Model):
    """Pre-defined targeting reports for casino member data"""
    
    name = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=50, default='casino')
    
    # Query criteria (to be applied to Member/Transaction models)
    query_criteria = models.JSONField(
        help_text='Targeting criteria: {"days_since_join": {"operator": "<=", "value": 7}}'
    )
    
    # Expected member count (cached)
    estimated_count = models.IntegerField(default=0)
    last_count_update = models.DateTimeField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'marketing_targeting_reports'
        verbose_name = 'Targeting Report'
        verbose_name_plural = 'Targeting Reports'
        ordering = ['name']
    
    def __str__(self):
        return f"📊 {self.name}"

# ================================
# CAMPAIGNS
# ================================

class Campaign(models.Model):
    """Marketing campaigns with anti-ban and targeting"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Basic information
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(CampaignCategory, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Target audience
    target_audience = models.ForeignKey(CustomAudience, on_delete=models.CASCADE)
    
    # Scheduling
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    
    # Anti-ban settings (can override tenant defaults)
    rate_limit_per_hour = models.IntegerField(default=20)
    min_delay_minutes = models.IntegerField(default=1)
    max_delay_minutes = models.IntegerField(default=5)
    messages_per_instance = models.IntegerField(default=50)
    rotate_instances = models.BooleanField(default=True)
    
    # Failed number handling (USER CHOICE)
    include_flagged_numbers = models.BooleanField(
        default=False, 
        help_text="Include numbers flagged as risky"
    )
    include_unverified_numbers = models.BooleanField(
        default=True, 
        help_text="Include numbers with unknown WhatsApp status"
    )
    max_retry_per_number = models.IntegerField(
        default=3, 
        help_text="Max retries for failed numbers"
    )
    
    # Campaign results and analytics
    total_targeted = models.IntegerField(default=0)
    total_queued = models.IntegerField(default=0)
    total_sent = models.IntegerField(default=0)
    total_delivered = models.IntegerField(default=0)
    total_failed = models.IntegerField(default=0)
    
    # Failure analysis
    failed_no_whatsapp = models.IntegerField(default=0)
    failed_blocked = models.IntegerField(default=0)
    failed_invalid_number = models.IntegerField(default=0)
    failed_other = models.IntegerField(default=0)
    
    # Performance metrics
    average_delivery_time = models.IntegerField(
        default=0, 
        help_text="Average delivery time in minutes"
    )
    cost_per_message = models.DecimalField(
        max_digits=6, 
        decimal_places=4, 
        default=0
    )
    total_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0
    )
    
    created_by = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'marketing_campaigns'
        verbose_name = 'Campaign'
        verbose_name_plural = 'Campaigns'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_by']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update category count
        if self.category_id:
            self.category.update_counts()
    
    @property
    def success_rate(self):
        """Calculate delivery success rate"""
        if self.total_sent == 0:
            return 0
        return round((self.total_delivered / self.total_sent) * 100, 1)
    
    @property
    def failure_rate_breakdown(self):
        """Get detailed failure analysis"""
        if self.total_failed == 0:
            return {}
        
        return {
            'no_whatsapp': round((self.failed_no_whatsapp / self.total_failed) * 100, 1),
            'blocked': round((self.failed_blocked / self.total_failed) * 100, 1),
            'invalid_number': round((self.failed_invalid_number / self.total_failed) * 100, 1),
            'other': round((self.failed_other / self.total_failed) * 100, 1),
        }
    
    def clean(self):
        """Validate campaign settings"""
        if self.end_date and self.start_date >= self.end_date:
            raise ValidationError("End date must be after start date")
        
        if self.min_delay_minutes >= self.max_delay_minutes:
            raise ValidationError("Min delay must be less than max delay")
        
    def generate_targets(self):
        """Generate campaign targets from audience"""
        from .models import CampaignTarget
        
        targets_created = 0
        audience = self.target_audience
        
        for member in audience.members:
            phone_number = member['phone_number']
            
            # Check if we should include this number
            if not self.include_flagged_numbers:
                try:
                    history = PhoneNumberHistory.objects.get(phone_number=phone_number)
                    if history.is_flagged or history.risk_level == 'high':
                        continue  # Skip flagged numbers
                except PhoneNumberHistory.DoesNotExist:
                    pass
            
            # Create target
            target, created = CampaignTarget.objects.get_or_create(
                campaign=self,
                phone_number=phone_number,
                defaults={
                    'member_data': member,
                    'status': 'queued'
                }
            )
            
            if created:
                targets_created += 1
        
        # Update campaign statistics
        self.total_targeted = targets_created
        self.save()
        
        return targets_created

class CampaignMessage(models.Model):
    """Link campaigns to message templates with weights"""
    
    campaign = models.ForeignKey(
        Campaign, 
        on_delete=models.CASCADE, 
        related_name='campaign_messages'
    )
    template = models.ForeignKey(MessageTemplate, on_delete=models.CASCADE)
    
    # A/B testing weight
    weight = models.IntegerField(
        default=100, 
        help_text="Selection weight (0-100)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'marketing_campaign_messages'
        verbose_name = 'Campaign Message'
        verbose_name_plural = 'Campaign Messages'
    
    def __str__(self):
        return f"{self.campaign.name} -> {self.template.name}"

class CampaignTarget(models.Model):
    """Individual phone numbers targeted by campaigns"""
    
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('scheduled', 'Scheduled'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
        ('excluded', 'Excluded'),
    ]
    
    campaign = models.ForeignKey(
        Campaign, 
        on_delete=models.CASCADE, 
        related_name='targets'
    )
    phone_number = models.CharField(max_length=20, db_index=True)
    
    # Member data snapshot
    member_data = models.JSONField(
        default=dict,
        help_text="Member data for template variables"
    )
    
    # Message details
    template_used = models.ForeignKey(
        MessageTemplate, 
        on_delete=models.SET_NULL, 
        null=True
    )
    final_message = models.TextField(
        blank=True, 
        help_text="Final processed message"
    )
    whatsapp_instance = models.CharField(max_length=100, blank=True)
    
    # Status and timing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    scheduled_time = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    # Error handling and retries
    error_message = models.TextField(blank=True)
    failure_reason = models.CharField(max_length=100, blank=True)
    retry_count = models.IntegerField(default=0)
    
    # External API tracking
    evolution_api_message_id = models.CharField(max_length=200, blank=True)
    evolution_api_response = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'marketing_campaign_targets'
        verbose_name = 'Campaign Target'
        verbose_name_plural = 'Campaign Targets'
        unique_together = ('campaign', 'phone_number')
        indexes = [
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['status', 'scheduled_time']),
            models.Index(fields=['phone_number']),
        ]
    
    def __str__(self):
        return f"{self.campaign.name} -> {self.phone_number} ({self.status})"
    
    def update_phone_history(self):
        """Update phone number history based on campaign result"""
        history, created = PhoneNumberHistory.objects.get_or_create(
            phone_number=self.phone_number
        )
        
        success = self.status == 'delivered'
        history.update_from_campaign_result(success, self.failure_reason)