# marketing_campaigns/forms.py

from django import forms
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Campaign, MessageTemplate, CustomAudience, CampaignCategory
from whatsapp_messaging.models import WhatsAppInstance

class CampaignForm(forms.ModelForm):
    """Form for creating and editing campaigns"""
    
    # Template selection
    template = forms.ModelChoiceField(
        queryset=MessageTemplate.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-control',
            'required': True
        }),
        help_text="Choose the message template for this campaign"
    )
    
    # Audience selection  
    target_audience = forms.ModelChoiceField(
        queryset=CustomAudience.objects.all(),
        widget=forms.Select(attrs={
            'class': 'form-control',
            'required': True
        }),
        help_text="Select the audience to send messages to"
    )
    
    # WhatsApp instance selection
    whatsapp_instance = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        widget=forms.Select(attrs={
            'class': 'form-control',
            'required': True
        }),
        help_text="Choose WhatsApp instance to send from"
    )
    
    # Scheduling
    start_immediately = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text="Start campaign immediately, or schedule for later"
    )
    
    start_date = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        }),
        help_text="When to start sending messages"
    )
    
    # Anti-ban settings
    rate_limit_per_hour = forms.IntegerField(
        initial=20,
        min_value=1,
        max_value=100,
        widget=forms.NumberInput(attrs={
            'class': 'form-control'
        }),
        help_text="Messages per hour (lower = safer)"
    )
    
    min_delay_minutes = forms.IntegerField(
        initial=1,
        min_value=0,
        max_value=30,
        widget=forms.NumberInput(attrs={
            'class': 'form-control'
        }),
        help_text="Minimum delay between messages (minutes)"
    )
    
    max_delay_minutes = forms.IntegerField(
        initial=5,
        min_value=1,
        max_value=60,
        widget=forms.NumberInput(attrs={
            'class': 'form-control'
        }),
        help_text="Maximum delay between messages (minutes)"
    )
    
    # Audience filtering options
    include_flagged_numbers = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text="Include phone numbers flagged as risky"
    )
    
    include_unverified_numbers = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text="Include numbers with unknown WhatsApp status"
    )
    
    class Meta:
        model = Campaign
        fields = [
            'name', 'description', 'category',
            'template', 'target_audience', 'whatsapp_instance',
            'start_immediately', 'start_date',
            'rate_limit_per_hour', 'min_delay_minutes', 'max_delay_minutes',
            'include_flagged_numbers', 'include_unverified_numbers'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., VIP Customer Welcome Campaign'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Brief description of this campaign...'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            })
        }
    
    def __init__(self, *args, **kwargs):
        # Get tenant_id from kwargs to filter WhatsApp instances
        tenant_id = kwargs.pop('tenant_id', None)
        super().__init__(*args, **kwargs)
        
        # Filter WhatsApp instances by tenant and only show connected ones
        if tenant_id:
            self.fields['whatsapp_instance'].queryset = WhatsAppInstance.objects.filter(
                tenant_id=tenant_id,
                is_active=True,
                status='connected'
            )
        else:
            self.fields['whatsapp_instance'].queryset = WhatsAppInstance.objects.none()
        
        # Set default start date to 5 minutes from now
        self.fields['start_date'].initial = timezone.now() + timedelta(minutes=5)
    
    def clean(self):
        cleaned_data = super().clean()
        start_immediately = cleaned_data.get('start_immediately')
        start_date = cleaned_data.get('start_date')
        min_delay = cleaned_data.get('min_delay_minutes', 0)
        max_delay = cleaned_data.get('max_delay_minutes', 0)
        
        # Validate scheduling
        if not start_immediately and not start_date:
            raise forms.ValidationError("Either start immediately or set a start date")
        
        if start_date and start_date <= timezone.now():
            raise forms.ValidationError("Start date must be in the future")
        
        # Validate delay settings
        if min_delay >= max_delay:
            raise forms.ValidationError("Minimum delay must be less than maximum delay")
        
        return cleaned_data
    
    def save(self, commit=True):
        campaign = super().save(commit=False)
        
        # Set start date based on start_immediately checkbox
        if self.cleaned_data.get('start_immediately'):
            campaign.start_date = timezone.now()
            campaign.status = 'running'
        else:
            campaign.start_date = self.cleaned_data.get('start_date')
            campaign.status = 'scheduled'
        
        if commit:
            campaign.save()
            
            # Create CampaignMessage link to template
            template = self.cleaned_data.get('template')
            if template:
                from .models import CampaignMessage
                CampaignMessage.objects.get_or_create(
                    campaign=campaign,
                    template=template,
                    defaults={'weight': 100}
                )
        
        return campaign

class MessageTemplateForm(forms.ModelForm):
    class Meta:
        model = MessageTemplate
        fields = ['name', 'description', 'category', 'content', 'variation_a', 'variation_b', 'use_variations']
        widgets = {
            'name': forms.TextInput(attrs={'style': 'width: 100%; padding: 8px;'}),
            'description': forms.Textarea(attrs={'style': 'width: 100%; padding: 8px; height: 60px;'}),
            'category': forms.Select(attrs={'style': 'width: 100%; padding: 8px;'}),
            'content': forms.Textarea(attrs={'style': 'width: 100%; padding: 8px; height: 120px;', 'placeholder': 'Enter your message. Use {{variable_name}} for dynamic content.'}),
            'variation_a': forms.Textarea(attrs={'style': 'width: 100%; padding: 8px; height: 100px;', 'placeholder': 'Alternative version A (optional)'}),
            'variation_b': forms.Textarea(attrs={'style': 'width: 100%; padding: 8px; height: 100px;', 'placeholder': 'Alternative version B (optional)'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active categories
        self.fields['category'].queryset = CampaignCategory.objects.filter(is_active=True)