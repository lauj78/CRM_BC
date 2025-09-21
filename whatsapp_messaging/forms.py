# whatsapp_messaging/forms.py

from django import forms
from .models import WhatsAppInstance

class WhatsappInstanceForm(forms.ModelForm):
    """
    A form for creating a WhatsAppInstance.
    It now uses ModelForm to automatically handle fields from the model
    and is configured to only require the 'instance_name' from the user.
    """
    class Meta:
        model = WhatsAppInstance
        fields = ['instance_name']
