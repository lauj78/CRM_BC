# tenants/templatetags/tenant_tags.py
from django import template

register = template.Library()

@register.filter
def endswith(value, suffix):
    """Custom filter to check if string ends with suffix"""
    if value and isinstance(value, str):
        return value.endswith(suffix)
    return False