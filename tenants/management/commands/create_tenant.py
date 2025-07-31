# tenants/management/commands/create_tenant.py
import re
import psycopg2
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connections
from django.core.management import call_command
from tenants.models import Tenant
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string

class Command(BaseCommand):
    help = 'Creates a new tenant database and admin user from email'
    
    def add_arguments(self, parser):
        parser.add_argument('admin_email', type=str, 
                           help='Full admin email (e.g., userx@mycrm.com)')

    def handle(self, *args, **options):
        admin_email = options['admin_email']
        
        # Validate email format
        if '@' not in admin_email:
            self.stderr.write(self.style.ERROR('Invalid email format'))
            return
            
        # Extract components
        username_part, domain = admin_email.split('@', 1)
        tenant_id = domain  # Use full domain as tenant ID
        
        # Sanitize for database name
        sanitized_db_name = re.sub(r'[^a-z0-9]', '_', domain.lower())
        db_name = f"crm_db_{sanitized_db_name}"
        
        # Generate credentials
        admin_password = get_random_string(12)
        postgres_password = input("Enter PostgreSQL 'postgres' user password: ")
        
        # Create database
        try:
            self.stdout.write("Connecting to PostgreSQL...")
            conn = psycopg2.connect(
                dbname="postgres",
                user="postgres",
                password=postgres_password,
                host="localhost"
            )
            conn.autocommit = True
            cursor = conn.cursor()
            
            # Create database
            cursor.execute(f"CREATE DATABASE {db_name}")
            self.stdout.write(self.style.SUCCESS(f"Created database: {db_name}"))
            
            # Grant privileges
            cursor.execute(f"""
                GRANT ALL PRIVILEGES ON DATABASE {db_name} 
                TO {settings.DATABASES['default']['USER']};
                
                GRANT CONNECT ON DATABASE {db_name} 
                TO {settings.DATABASES['default']['USER']};
                
                GRANT USAGE ON SCHEMA public 
                TO {settings.DATABASES['default']['USER']};
                
                GRANT CREATE ON SCHEMA public 
                TO {settings.DATABASES['default']['USER']};
                
                ALTER DEFAULT PRIVILEGES IN SCHEMA public 
                GRANT ALL PRIVILEGES ON TABLES 
                TO {settings.DATABASES['default']['USER']};
            """)
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Database operation failed: {str(e)}"))
            return
        finally:
            if 'cursor' in locals(): cursor.close()
            if 'conn' in locals(): conn.close()

        # Configure database connection
        connections.databases[db_name] = {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': db_name,
            'USER': settings.DATABASES['default']['USER'],
            'PASSWORD': settings.DATABASES['default']['PASSWORD'],
            'HOST': 'localhost',
            'PORT': '5432',
            'OPTIONS': {'options': '-c search_path=public'},
        }

        # Run migrations
        try:
            self.stdout.write("Running database migrations...")
            call_command('migrate', database=db_name)
            self.stdout.write(self.style.SUCCESS("Migrations completed"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Migration failed: {str(e)}"))
            self.stderr.write("Please run migrations manually:")
            self.stderr.write(f"python manage.py migrate --database={db_name}")
            return

        # Create tenant record
        try:
            tenant = Tenant.objects.create(
                tenant_id=tenant_id,
                name=f"{domain.capitalize()} Tenant",
                db_alias=db_name,
                contact_email=admin_email
            )
            self.stdout.write(self.style.SUCCESS(f"Created tenant record: {tenant_id}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Tenant creation failed: {str(e)}"))
            return

        # Create admin user
        try:
            User = get_user_model()
            username = admin_email  # Use full email as username
            user = User.objects.using(db_name).create(
                username=username,
                email=admin_email,
                is_staff=True,
                is_superuser=True
            )
            user.set_password(admin_password)
            user.save()
            
            self.stdout.write("\n" + "="*50)
            self.stdout.write(self.style.SUCCESS("TENANT CREATED SUCCESSFULLY"))
            self.stdout.write("="*50)
            self.stdout.write(f"Tenant ID: {tenant_id}")
            self.stdout.write(f"Database: {db_name}")
            self.stdout.write(f"Admin username: {username}")
            self.stdout.write(f"Admin password: {admin_password}")
            self.stdout.write("\nAdd this to DATABASES in settings.py:")
            self.stdout.write(self.style.WARNING(
                f"'{db_name}': {{\n"
                f"    'ENGINE': 'django.db.backends.postgresql',\n"
                f"    'NAME': '{db_name}',\n"
                f"    'USER': '{settings.DATABASES['default']['USER']}',\n"
                f"    'PASSWORD': '{settings.DATABASES['default']['PASSWORD']}',\n"
                f"    'HOST': 'localhost',\n"
                f"    'PORT': '5432',\n"
                f"    'OPTIONS': {{'options': '-c search_path=public'}},\n"
                "}},"
            ))
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"User creation failed: {str(e)}"))
            return