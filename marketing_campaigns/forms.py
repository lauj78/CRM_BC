# marketing_campaigns/forms.py
from django import forms
from .models import MessageTemplate, CampaignCategory

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