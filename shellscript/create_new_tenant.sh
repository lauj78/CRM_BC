#!/bin/bash

if [ $# -ne 2 ]; then
    echo "Usage: $0 <tenant_id> <tenant_name>"
    echo "Example: $0 newcompany.com 'New Company'"
    exit 1
fi

TENANT_ID=$1
TENANT_NAME=$2
DB_NAME="crm_db_${TENANT_ID//./_}"

echo "Creating tenant: $TENANT_NAME"
echo "Database: $DB_NAME"
echo ""

# Stop services
echo "1. Stopping services..."
sudo systemctl stop gunicorn celery celerybeat

# Create database from template
echo "2. Creating database from template..."
sudo -u postgres psql << SQL
CREATE DATABASE $DB_NAME WITH TEMPLATE crm_db_template OWNER crm_user;

\c $DB_NAME
GRANT ALL ON SCHEMA public TO crm_user;
GRANT CREATE ON SCHEMA public TO crm_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO crm_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO crm_user;
SQL

# Clear users and create new admin
echo "3. Creating admin user..."
cd ~/crm_project
source venv/bin/activate

python manage.py shell << PYTHON
from django.contrib.auth import get_user_model
User = get_user_model()

# Delete all users from template
User.objects.using('$DB_NAME').all().delete()

# Create new admin
User.objects.db_manager('$DB_NAME').create_superuser(
    username='admin@$TENANT_ID',
    email='admin@$TENANT_ID',
    password='admin123',
    first_name='Admin',
    last_name='$TENANT_NAME'
)
print("✅ Admin created")
PYTHON

# Create tenant record
echo "4. Creating tenant record..."
python manage.py shell << PYTHON
from tenants.models import Tenant

Tenant.objects.create(
    tenant_id='$TENANT_ID',
    name='$TENANT_NAME',
    db_alias='$DB_NAME',
    is_active=True
)
print("✅ Tenant record created")
PYTHON

# Start services
echo "5. Starting services..."
sudo systemctl start gunicorn celery celerybeat

echo ""
echo "✅ DONE!"
echo ""
echo "Tenant: $TENANT_NAME"
echo "URL: https://mingyuancrm.ddns.net/?tenant=$TENANT_ID"
echo "Username: admin"
echo "Password: admin123"
