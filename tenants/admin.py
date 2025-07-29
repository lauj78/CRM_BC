from django.contrib import admin
from .models import Tenant

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant_id', 'db_alias', 'is_active', 'subscription_start', 'subscription_end', 'days_remaining_display')
    list_editable = ('subscription_end', 'is_active')
    list_filter = ('is_active', 'subscription_end')
    search_fields = ('name', 'tenant_id')
    fieldsets = (
        (None, {
            'fields': ('name', 'tenant_id', 'db_alias', 'is_active')
        }),
        ('Subscription Dates', {
            'fields': ('subscription_start', 'subscription_end')
        }),
        ('Contact Information', {
            'fields': ('contact_email', 'contact_phone'),
            'classes': ('collapse',)
        }),
    )
    def days_remaining_display(self, obj):
        return obj.days_remaining
    days_remaining_display.short_description = 'Days Remaining'