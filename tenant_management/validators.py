from django.core.exceptions import ValidationError
from tenants.models import Tenant

def validate_tenant_email(value, tenant_id):
    """
    Validate that email ends with @<tenant_id> or @master
    """
    # Allow master domain in any context
    if value.endswith('@master'):
        return
    
    # Extract domain from email
    domain = value.split('@')[-1] if '@' in value else ''
    
    # Validate against tenant ID
    if domain != tenant_id:
        raise ValidationError(
            f"Email must end with @{tenant_id}. You entered: {value}",
            code='invalid_tenant_email'
        )