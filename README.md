

*******************************************************
*** This is the ReadMe file for setup of the system ***
*******************************************************

Under folder shellscript  is all useful sh script for backup and create new tenant.
this include the new version of evolutionapi setup docker yml and .env file.


and below is the step and command we use to create system. :

********************************************************



cat > ~/crm_project/README.md << 'EOF'
# Multi-Tenant CRM System

A Django-based multi-tenant Customer Relationship Management system with WhatsApp integration, marketing campaigns, and member management.

---

## 🎯 Features

- **Multi-tenant architecture** - Each tenant has isolated database
- **WhatsApp Integration** - Send/receive messages via Evolution API
- **Member Management** - Track members, transactions, payments
- **Marketing Campaigns** - Create and manage marketing campaigns
- **Background Tasks** - Celery for async processing
- **Admin Dashboard** - Django admin for each tenant

---

## 📋 Prerequisites

- **OS**: Ubuntu 22.04+ or Debian 11+
- **Python**: 3.11+
- **PostgreSQL**: 15+
- **Redis**: 7+
- **Nginx**: Latest
- **Docker**: Latest (for Evolution API)
- **Memory**: Minimum 4GB RAM
- **Storage**: Minimum 20GB

---

## 🚀 Installation

### 1. System Dependencies
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install -y python3.13 python3.13-venv python3-pip

# Install PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Install Redis
sudo apt install -y redis-server

# Install Nginx
sudo apt install -y nginx

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo apt install -y docker-compose-plugin
```

### 2. PostgreSQL Setup
```bash
# Create database user
sudo -u postgres psql << EOF
CREATE USER crm_user WITH PASSWORD 'crm_password';
ALTER USER crm_user CREATEDB;
CREATE DATABASE crm_db OWNER crm_user;
EOF

# Grant schema permissions (PostgreSQL 15+ requirement)
sudo -u postgres psql -d crm_db << EOF
GRANT ALL ON SCHEMA public TO crm_user;
GRANT CREATE ON SCHEMA public TO crm_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO crm_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO crm_user;
EOF
```

### 3. Project Setup
```bash
# Clone/upload project to server
cd ~
# (Upload your project to ~/crm_project)

# Create virtual environment
cd ~/crm_project
python3.13 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
# Create .env file
nano ~/crm_project/.env
```

**Add these settings:**
```env
SECRET_KEY=your-secret-key-here-change-this
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# Database
DB_NAME=crm_db
DB_USER=crm_user
DB_PASSWORD=crm_password
DB_HOST=localhost
DB_PORT=5432

# Evolution API
EVOLUTION_API_URL=http://localhost:8081
EVOLUTION_API_KEY=your-api-key-here

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### 5. Run Migrations
```bash
cd ~/crm_project
source venv/bin/activate

# Run migrations on default database
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### 6. Setup Gunicorn Service
```bash
sudo nano /etc/systemd/system/gunicorn.service
```

**Add:**
```ini
[Unit]
Description=Gunicorn daemon for CRM
After=network.target

[Service]
User=your-username
Group=www-data
WorkingDirectory=/home/your-username/crm_project
Environment="PATH=/home/your-username/crm_project/venv/bin"
ExecStart=/home/your-username/crm_project/venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/home/your-username/crm_project/crm_project.sock \
    crm_project.wsgi:application

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
```

### 7. Setup Celery Services
```bash
# Celery Worker
sudo nano /etc/systemd/system/celery.service
```
```ini
[Unit]
Description=Celery Service
After=network.target

[Service]
Type=forking
User=your-username
Group=www-data
WorkingDirectory=/home/your-username/crm_project
Environment="PATH=/home/your-username/crm_project/venv/bin"
ExecStart=/home/your-username/crm_project/venv/bin/celery -A crm_project worker --loglevel=info --detach

[Install]
WantedBy=multi-user.target
```
```bash
# Celery Beat
sudo nano /etc/systemd/system/celerybeat.service
```
```ini
[Unit]
Description=Celery Beat Service
After=network.target

[Service]
Type=simple
User=your-username
Group=www-data
WorkingDirectory=/home/your-username/crm_project
Environment="PATH=/home/your-username/crm_project/venv/bin"
ExecStart=/home/your-username/crm_project/venv/bin/celery -A crm_project beat --loglevel=info

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl start celery celerybeat
sudo systemctl enable celery celerybeat
```

### 8. Nginx Configuration
```bash
sudo nano /etc/nginx/sites-available/crm
```
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /static/ {
        alias /home/your-username/crm_project/staticfiles/;
    }

    location /media/ {
        alias /home/your-username/crm_project/media/;
    }

    location / {
        proxy_pass http://unix:/home/your-username/crm_project/crm_project.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Enable site:**
```bash
sudo ln -s /etc/nginx/sites-available/crm /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 9. SSL Certificate
```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d your-domain.com
```

---

## 📦 Evolution API Setup (WhatsApp)

### Option 1: Docker Setup (Recommended)
```bash
mkdir -p ~/evolution-api
cd ~/evolution-api

# Create docker-compose.yml
nano docker-compose.yml
```

**Add:**
```yaml
version: '3.8'

services:
  api:
    image: evoapicloud/evolution-api:latest
    container_name: evolution_api
    restart: always
    ports:
      - "127.0.0.1:8081:8080"
    depends_on:
      - redis
      - postgres
    environment:
      - SERVER_URL=http://localhost:8081
      - DATABASE_PROVIDER=postgresql
      - DATABASE_URL=postgresql://evolution:evolution123@postgres:5432/evolution
      - DATABASE_CONNECTION_URI=postgresql://evolution:evolution123@postgres:5432/evolution
      - CACHE_REDIS_ENABLED=true
      - CACHE_REDIS_URI=redis://redis:6379/6
      - AUTHENTICATION_API_KEY=your-api-key-here
    volumes:
      - evolution_instances:/evolution/instances
    networks:
      - evolution

  redis:
    image: redis:latest
    container_name: evolution_redis
    command: redis-server --appendonly yes
    restart: always
    volumes:
      - evolution_redis:/data
    networks:
      - evolution

  postgres:
    image: postgres:16-alpine
    container_name: evolution_postgres
    restart: always
    environment:
      - POSTGRES_USER=evolution
      - POSTGRES_PASSWORD=evolution123
      - POSTGRES_DB=evolution
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - evolution

volumes:
  evolution_instances:
  evolution_redis:
  postgres_data:

networks:
  evolution:
    driver: bridge
```

**Start services:**
```bash
docker compose up -d
docker logs evolution_api -f
```

---

## 👥 Tenant Management

### Create Template Database (One-time)
```bash
# After setting up first tenant with clean data
sudo systemctl stop gunicorn celery celerybeat

sudo -u postgres psql << 'EOF'
CREATE DATABASE crm_db_template WITH TEMPLATE crm_db_clean OWNER crm_user;
UPDATE pg_database SET datistemplate = TRUE WHERE datname = 'crm_db_template';

\c crm_db_template
GRANT ALL ON SCHEMA public TO crm_user;
GRANT CREATE ON SCHEMA public TO crm_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO crm_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO crm_user;
EOF

sudo systemctl start gunicorn celery celerybeat
```

### Create New Tenant (Automated Script)
```bash
# Use the provided script
~/create_new_tenant.sh company.com "Company Name"
```

**Script location:** `~/create_new_tenant.sh`

### Manual Tenant Creation
```bash
# 1. Create database
sudo -u postgres psql << EOF
CREATE DATABASE crm_db_company_com WITH TEMPLATE crm_db_template OWNER crm_user;

\c crm_db_company_com
GRANT ALL ON SCHEMA public TO crm_user;
GRANT CREATE ON SCHEMA public TO crm_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO crm_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO crm_user;
EOF

# 2. Create admin user
python manage.py shell << 'PYTHON'
from django.contrib.auth import get_user_model
User = get_user_model()

User.objects.db_manager('crm_db_company_com').create_superuser(
    username='admin',
    email='admin@company.com',
    password='admin123'
)
PYTHON

# 3. Create tenant record
python manage.py shell << 'PYTHON'
from tenants.models import Tenant

Tenant.objects.create(
    tenant_id='company.com',
    name='Company Name',
    db_alias='crm_db_company_com',
    is_active=True
)
PYTHON

# 4. Restart services
sudo systemctl restart gunicorn celery celerybeat
```

---

## ⚙️ Common Commands

### Service Management
```bash
# Restart all services
sudo systemctl restart gunicorn celery celerybeat nginx

# Check status
sudo systemctl status gunicorn
sudo systemctl status celery
sudo systemctl status celerybeat

# View logs
sudo journalctl -u gunicorn -f
sudo journalctl -u celery -f
```

### Database Operations
```bash
# Connect to PostgreSQL
sudo -u postgres psql

# List databases
\l

# Connect to specific database
\c crm_db_company_com

# List tables
\dt

# Exit
\q
```

### Django Management
```bash
cd ~/crm_project
source venv/bin/activate

# Run migrations
python manage.py migrate --database=crm_db_company_com

# Create superuser for specific tenant
python manage.py shell
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> User.objects.db_manager('crm_db_company_com').create_superuser(
...     username='admin',
...     email='admin@company.com',
...     password='password123'
... )

# Collect static files
python manage.py collectstatic --noinput

# Check for errors
python manage.py check
```

### Evolution API Management
```bash
# View logs
docker logs evolution_api -f

# Restart Evolution API
docker restart evolution_api

# Stop/Start
docker stop evolution_api
docker start evolution_api

# Check instances
curl -X GET "http://localhost:8081/instance/fetchInstances" \
  -H "apikey: your-api-key"
```

---

## ⚠️ Important Notes & Gotchas

### PostgreSQL 15+ Permissions Issue

**Problem:** `permission denied for schema public`

**Solution:** Always grant schema permissions when creating new databases:
```bash
sudo -u postgres psql -d DATABASE_NAME << EOF
GRANT ALL ON SCHEMA public TO crm_user;
GRANT CREATE ON SCHEMA public TO crm_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO crm_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO crm_user;
EOF
```

### Settings.py Database Configuration

**Must include all tenant databases:**
```python
DATABASES = {
    'default': {...},
    'crm_db_company_com': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'crm_db_company_com',
        'USER': 'crm_user',
        'PASSWORD': 'crm_password',
        'HOST': 'localhost',
        'PORT': '5432',
    },
    # Add each tenant database
}
```

### Evolution API Image

**Use the correct Docker image:**
- ✅ `evoapicloud/evolution-api:latest` - Works on DigitalOcean
- ❌ `atendai/evolution-api:latest` - May have connection issues

### Firewall Configuration
```bash
# Allow necessary ports
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

### File Permissions
```bash
# Set correct ownership
sudo chown -R your-username:www-data ~/crm_project
sudo chmod -R 755 ~/crm_project

# Socket file permissions
sudo chown your-username:www-data ~/crm_project/crm_project.sock
```

---

## 🐛 Troubleshooting

### Gunicorn Won't Start
```bash
# Check logs
sudo journalctl -u gunicorn -n 50

# Test manually
cd ~/crm_project
source venv/bin/activate
gunicorn --bind 0.0.0.0:8000 crm_project.wsgi:application
```

### Database Connection Issues
```bash
# Test PostgreSQL connection
psql -U crm_user -h localhost -d crm_db

# Check if PostgreSQL is running
sudo systemctl status postgresql
```

### Evolution API Not Working
```bash
# Check Docker containers
docker ps

# View Evolution API logs
docker logs evolution_api --tail=100

# Restart Evolution API
docker restart evolution_api
```

### Migration Errors
```bash
# If migrations fail, check migration state
python manage.py showmigrations --database=crm_db_company_com

# Fake migrations if needed (careful!)
python manage.py migrate --fake --database=crm_db_company_com
```

### Clean All Data From Tenant (Keep Structure)
```bash
sudo -u postgres psql -d crm_db_company_com << 'EOF'
DELETE FROM marketing_campaign_targets;
DELETE FROM marketing_campaign_messages;
DELETE FROM marketing_campaigns;
DELETE FROM data_management_transaction;
DELETE FROM data_management_member;
DELETE FROM wa_whatsappinstance;
DELETE FROM django_session;
DELETE FROM django_admin_log;
DELETE FROM auth_user WHERE username != 'admin';
EOF
```

---

## 📊 System Monitoring

### Check System Resources
```bash
# Memory usage
free -h

# Disk usage
df -h

# Service status
~/check_system.sh  # If you have the monitoring script
```

### Database Size
```bash
sudo -u postgres psql -c "
SELECT 
    datname, 
    pg_size_pretty(pg_database_size(datname)) 
FROM pg_database 
WHERE datname LIKE 'crm_db%';"
```

### Log Rotation

Logs are automatically rotated. Check:
```bash
ls -lh ~/crm_project/logs/
```

---

## 🔐 Security Recommendations

1. **Change default passwords** in production
2. **Use strong SECRET_KEY** in Django settings
3. **Enable firewall** (ufw)
4. **Keep system updated**: `sudo apt update && sudo apt upgrade`
5. **Regular backups** of databases
6. **SSL certificates** for all domains
7. **Restrict database access** to localhost only

---

## 📦 Backup & Restore

### Backup Database
```bash
# Backup single tenant
sudo -u postgres pg_dump crm_db_company_com > backup_company_$(date +%Y%m%d).sql

# Backup all databases
~/backup_databases.sh  # If you have the backup script
```

### Restore Database
```bash
# Restore from backup
sudo -u postgres psql crm_db_company_com < backup_company_20250101.sql
```

---

## 📝 Project Structure
```
crm_project/
├── crm_project/          # Main Django project
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── tenants/              # Tenant management app
├── data_management/      # Members, transactions
├── whatsapp_messaging/   # WhatsApp integration
├── marketing_campaigns/  # Marketing features
├── manage.py
├── requirements.txt
└── README.md
```

---

## 🆘 Support

For issues or questions:
1. Check logs: `sudo journalctl -u gunicorn -f`
2. Review this README
3. Check Django documentation
4. Contact system administrator

---

## 📄 License

[Your License Here]

---

**Version:** 1.0  
**Last Updated:** October 2025
EOF

echo "✅ README.md created!"