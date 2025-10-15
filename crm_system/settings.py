"""
Django settings for crm_system project.
Production-ready with environment variable configuration.
"""

import os
from pathlib import Path
from decouple import config, Csv

# Build paths inside the project like this: BASE_DIR / 'subdir'
BASE_DIR = Path(__file__).resolve().parent.parent

# Security Settings
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())

# Login/Logout URLs
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = 'tenant_redirect'
LOGOUT_REDIRECT_URL = '/accounts/login/'
AUTHENTICATED_REDIRECT_URL = 'tenant_redirect'

# Custom error handlers
handler404 = 'crm_system.views.custom_404'

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django_celery_beat',
    'django_celery_results',
    'data_management',
    'dashboard_app',
    'report_app',
    'tenants', 
    'tenant_management',
    'whatsapp_messaging',
    'marketing_campaigns',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'tenants.middleware.BackendSessionMiddleware',
    'tenants.middleware.TenantBypassMiddleware',
    'tenants.middleware.TenantMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'tenants.middleware.ResponseSafetyMiddleware',
    'tenants.middleware.SecurityLoggerMiddleware',
    'tenants.subscription_middleware.SubscriptionMiddleware',   
]

ROOT_URLCONF = 'crm_system.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'crm_system.wsgi.application'

# Database Configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'OPTIONS': {
            'options': '-c search_path=public'
        },
    },
    'crm_db_pukul_com': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_TENANT_PUKUL_NAME', default='crm_db_pukul_com'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'OPTIONS': {
            'options': '-c search_path=public'
        },
    },
    'crm_db_test_com': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_TENANT_TEST_NAME', default='crm_db_test_com'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'OPTIONS': {
            'options': '-c search_path=public'
        },
    },
}

# Database router for tenant isolation
DATABASE_ROUTERS = ['tenants.db_router.DatabaseTenantRouter']

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

AUTHENTICATION_BACKENDS = [
    'tenants.backends.TenantAuthBackend',
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = config('TIME_ZONE', default='UTC')
USE_I18N = True
USE_TZ = False

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Session Configuration
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_SECURE = not DEBUG  # True in production (HTTPS)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_NAME = "crm_session"
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_AGE = 3600  # 1 hour

# Tenant Configuration
PUBLIC_APPS = ['admin', 'auth', 'contenttypes', 'sessions', 'tenants']
TENANT_APPS = ['data_management', 'dashboard_app', 'report_app', 'marketing_campaigns', 'whatsapp_messaging']

AUTH_USER_MODEL = "auth.User"

# Site URL (for webhooks)
SITE_URL = config('SITE_URL')

# WhatsApp Evolution API Configuration
EVOLUTION_API_CONFIG = {
    'BASE_URL': config('EVOLUTION_API_URL', default='http://localhost:8081'),
    'API_KEY': config('EVOLUTION_API_KEY'),
    'DEFAULT_TIMEOUT': 30,
    'MAX_INSTANCES': 20,
    'DEFAULT_MESSAGE_LIMIT': 200,
}

# Message Queue Settings
MESSAGE_QUEUE_CONFIG = {
    'MAX_RETRY_ATTEMPTS': 3,
    'RETRY_DELAY': 300,
    'BATCH_SIZE': 50,
    'RATE_LIMIT_PER_INSTANCE': 50,
}

# Celery Configuration
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 240

# Production Security Settings (only when DEBUG=False)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '[{levelname}] {asctime} {module}: {message}',
            'style': '{',
        },
        'detailed': {
            'format': '[{levelname}] {asctime} {name} {module}.{funcName}:{lineno} - {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'app.log'),
            'formatter': 'detailed',
        },
    },
    'loggers': {
        'marketing_campaigns': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'whatsapp_messaging': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'data_management': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'tenants': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': [],
            'level': 'ERROR',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
}