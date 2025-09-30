# marketing_campaigns/forms.py - Updated with Option 3 (no category selection)

from django import forms
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Campaign, MessageTemplate, CustomAudience, CampaignCategory, CampaignMessage
from whatsapp_messaging.models import WhatsAppInstance

class CampaignForm(forms.ModelForm):
    """Form for creating and editing campaigns - SIMPLIFIED (anti-ban handled by service)"""
    
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
    
    # Scheduling
    start_immediately = forms.BooleanField(
        required=False,
        initial=True,
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
    
    # Audience filtering options
    include_flagged_numbers = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text="Include phone numbers flagged as risky"
    )
    
    include_whatsapp_verified = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input whatsapp-filter',
            'data-status': 'confirmed'
        }),
        help_text="Include numbers confirmed to have WhatsApp"
    )
    
    include_non_whatsapp = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input whatsapp-filter',
            'data-status': 'not_available'
        }),
        help_text="Include numbers without WhatsApp"
    )
    
    include_unverified_numbers = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input whatsapp-filter',
            'data-status': 'unknown'
        }),
        help_text="Include numbers not yet verified"
    )
    
    class Meta:
        model = Campaign
        fields = [
            'name', 'description',
            'template', 'target_audience',
            'start_immediately', 'start_date',
            'include_whatsapp_verified', 'include_non_whatsapp',
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
            })
        }
    
    def __init__(self, *args, **kwargs):
        tenant_id = kwargs.pop('tenant_id', None)
        super().__init__(*args, **kwargs)
        
        # Set default start date to 5 minutes from now
        self.fields['start_date'].initial = timezone.now() + timedelta(minutes=5)
    
    def clean(self):
        cleaned_data = super().clean()
        start_immediately = cleaned_data.get('start_immediately')
        start_date = cleaned_data.get('start_date')
        
        # Validate scheduling
        if not start_immediately and not start_date:
            raise forms.ValidationError("Either start immediately or set a start date")
        
        if start_date and start_date <= timezone.now():
            raise forms.ValidationError("Start date must be in the future")
        
        return cleaned_data
    
    def save(self, commit=True):
        campaign = super().save(commit=False)
        
        # AUTO-ASSIGN DEFAULT CATEGORY
        if not campaign.category_id:
            default_category, created = CampaignCategory.objects.get_or_create(
                name='General',
                defaults={
                    'description': 'Default category for all campaigns and templates',
                    'color': '#007bff',
                    'icon': 'folder',
                    'is_system_default': True,
                    'is_active': True
                }
            )
            campaign.category = default_category
        
        # Set scheduling
        if self.cleaned_data.get('start_immediately'):
            campaign.start_date = timezone.now()
            campaign.status = 'running'
        else:
            campaign.start_date = self.cleaned_data.get('start_date')
            campaign.status = 'scheduled'
        
        # Anti-ban settings will use tenant defaults (no longer set on campaign)
        # Remove these fields from Campaign or leave them NULL
        
        if commit:
            campaign.save()
            
            # Create CampaignMessage link to template
            template = self.cleaned_data.get('template')
            if template:
                CampaignMessage.objects.get_or_create(
                    campaign=campaign,
                    template=template,
                    defaults={'weight': 100}
                )
        
        return campaign    
        

class MessageTemplateForm(forms.ModelForm):
    """Form for creating/editing message templates - no category selection"""
    
    class Meta:
        model = MessageTemplate
        fields = ['name', 'description', 'content', 'variation_a', 'variation_b', 'use_variations']  # REMOVED 'category'
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'style': 'width: 100%; padding: 8px;',
                'placeholder': 'Enter template name (e.g., Welcome Bonus)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'style': 'width: 100%; padding: 8px; height: 60px;',
                'placeholder': 'Brief description of this template'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'style': 'width: 100%; padding: 8px; height: 120px;', 
                'placeholder': 'Enter your message. Use {{variable_name}} for dynamic content.'
            }),
            'variation_a': forms.Textarea(attrs={
                'class': 'form-control',
                'style': 'width: 100%; padding: 8px; height: 100px;', 
                'placeholder': 'Alternative version A (optional for anti-ban)'
            }),
            'variation_b': forms.Textarea(attrs={
                'class': 'form-control',
                'style': 'width: 100%; padding: 8px; height: 100px;', 
                'placeholder': 'Alternative version B (optional for anti-ban)'
            }),
            'use_variations': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # No longer need to filter categories since we're not showing the field
    
    def save(self, commit=True):
        template = super().save(commit=False)
        
        # AUTO-ASSIGN DEFAULT CATEGORY (Option 3 implementation)
        if not template.category_id:
            default_category, created = CampaignCategory.objects.get_or_create(
                name='General',
                defaults={
                    'description': 'Default category for all campaigns and templates',
                    'color': '#007bff',
                    'icon': 'folder',
                    'is_system_default': True,
                    'is_active': True
                }
            )
            template.category = default_category
        
        if commit:
            template.save()
        
        return template