# test_webhook_simple.py - Save this as a file in your project root

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm_system.settings')
django.setup()

import requests
import json
from datetime import datetime
from whatsapp_messaging.models import WhatsAppInstance
from tenants.models import Tenant

# Get a tenant and instance from your database
tenant = Tenant.objects.get(tenant_id='pukul.com')  # Replace with your tenant
db_alias = f'crm_db_pukul_com'

# Get an instance from that tenant
instance = WhatsAppInstance.objects.using(db_alias).filter(status='connected').first()

if not instance:
    print("No connected instance found! Trying any instance...")
    instance = WhatsAppInstance.objects.using(db_alias).first()

if not instance:
    print("No WhatsApp instance found in database!")
    exit()

print(f"Using instance: {instance.instance_name}")
print(f"External ID: {instance.external_id}")
print(f"API Key: {instance.api_key}")

# Configuration
WEBHOOK_URL = "http://localhost:8000/api/whatsapp/webhooks/evolution/"  # Change if different
TEST_CUSTOMER_PHONE = "601113191736"  # A test phone number (change to any number)

# Create test payload (simulating a customer message)
test_payload = {
    "instanceId": instance.external_id,  # From your database
    "event": "messages.upsert",
    "data": {
        "key": {
            "remoteJid": f"{TEST_CUSTOMER_PHONE}@s.whatsapp.net",  # Customer's phone
            "fromMe": False,  # False = from customer, True = from you
            "id": f"TEST_{datetime.now().timestamp()}"
        },
        "message": {
            "conversation": "Test message from debug script"
        }
    }
}

# Headers with your instance's API key
headers = {
    "Content-Type": "application/json",
    "x-api-key": instance.api_key  # From your database
}

print(f"\n--- SENDING TEST WEBHOOK ---")
print(f"URL: {WEBHOOK_URL}")
print(f"Instance: {instance.instance_name}")
print(f"Simulating message from: {TEST_CUSTOMER_PHONE}")

try:
    response = requests.post(WEBHOOK_URL, json=test_payload, headers=headers)
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("\n✅ Webhook accepted! Check your inbox for the test message.")
        print(f"Check: http://localhost:8000/tenant/{tenant.tenant_id}/marketing/inbox/")
    else:
        print("\n❌ Webhook failed. Check your logs for details.")
        
except Exception as e:
    print(f"\n❌ Error sending request: {e}")
    print("Make sure your Django server is running!")