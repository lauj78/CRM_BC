from django import forms
from django.contrib.auth import get_user_model
from .validators import validate_tenant_email
from tenants.models import Tenant

User = get_user_model()

class TenantUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'is_active']
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant')  # Tenant object passed from view
        super().__init__(*args, **kwargs)
    
    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        validate_tenant_email(email, self.tenant.tenant_id)
        
        # Check unique within tenant database
        if User.objects.using(self.tenant.db_alias).filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Email already exists for this tenant")
        
        return email

class TenantUserCreateForm(TenantUserForm):
    password = forms.CharField(widget=forms.PasswordInput)
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save(using=self.tenant.db_alias)
        return user
    
class AdminPasswordResetForm(forms.Form):
    new_password1 = forms.CharField(
        label="New password",
        widget=forms.PasswordInput,
        help_text="Enter the new password"
    )
    new_password2 = forms.CharField(
        label="Confirm new password",
        widget=forms.PasswordInput,
        help_text="Enter the same password as above for verification"
    )

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("new_password1")
        password2 = cleaned_data.get("new_password2")
        
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("The two password fields didn't match.")
        
        return cleaned_data