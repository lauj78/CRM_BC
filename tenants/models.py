from django.db import models

class Tenant(models.Model):
    tenant_id = models.CharField(max_length=100, unique=True, help_text="Unique identifier for the tenant (e.g., pukul69)")
    name = models.CharField(max_length=100, help_text="Name of the tenant/customer")
    db_alias = models.CharField(max_length=100, help_text="Database alias from settings (e.g., crm_db_pukul69)")
    created_on = models.DateField(auto_now_add=True, help_text="Date the tenant was created")

    def __str__(self):
        return self.name