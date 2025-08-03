from django.db import models
from tenants.models import Tenant  # Add this import


# Create your models here.

class Member(models.Model):
    username = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    referral = models.CharField(max_length=100, blank=True)
    handphone = models.CharField(max_length=20)
    join_date = models.DateTimeField()
    email = models.EmailField(blank=True)

    def __str__(self):
        return self.username

class Transaction(models.Model):
    EVENT_CHOICES = [
        ('Deposit', 'Deposit'),
        ('Withdraw', 'Withdraw'),
    ]
    username = models.CharField(max_length=100)
    event = models.CharField(max_length=20, choices=EVENT_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    create_date = models.DateTimeField()
    process_date = models.DateTimeField()
    process_by = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ('username', 'event', 'create_date', 'amount')

    def __str__(self):
        return f"{self.event} by {self.username}"
     
    
class ErrorLog(models.Model):
    # Cross-database foreign key - disable DB constraint
    tenant = models.ForeignKey(
        Tenant, 
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_constraint=False  # This allows cross-database relationships
    )
    
    file_name = models.CharField(max_length=100, unique=True)
    file_path = models.CharField(max_length=200)
    upload_time = models.DateTimeField()
    file_type = models.CharField(max_length=20)
    error_count = models.IntegerField()
    success_count = models.IntegerField()

    def __str__(self):
        return self.file_name