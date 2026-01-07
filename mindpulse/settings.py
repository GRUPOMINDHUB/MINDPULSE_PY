"""
Mindpulse Django Settings
Plataforma SaaS Multi-tenant para Gestão de Equipes
"""

import os
from pathlib import Path
from decouple import config, Csv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

# Permite acesso local em qualquer interface de rede
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,0.0.0.0', cast=Csv())

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    
    # Third-party apps
    'widget_tweaks',
    'crispy_forms',
    'crispy_tailwind',
    'django_extensions',
    
    # Local apps
    'apps.core',
    'apps.accounts',
    'apps.trainings',
    'apps.checklists',
    'apps.feedback',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.CompanyMiddleware',
    'apps.core.middleware.SubscriptionGateMiddleware',
]

ROOT_URLCONF = 'mindpulse.urls'

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
                'apps.core.context_processors.company_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'mindpulse.wsgi.application'

# =============================================================================
# DATABASE CONFIGURATION - PostgreSQL (Google Cloud SQL) ou SQLite
# =============================================================================
# Para desenvolvimento local com SQLite (padrão para facilitar setup)
USE_SQLITE = config('USE_SQLITE', default=True, cast=bool)

if USE_SQLITE:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    # PostgreSQL para produção (Google Cloud SQL)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME', default='mindpulse_db'),
            'USER': config('DB_USER', default='postgres'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': config('DB_HOST', default='127.0.0.1'),
            'PORT': config('DB_PORT', default='5432'),
            'OPTIONS': {
                'connect_timeout': 10,
            },
        }
    }

# =============================================================================
# AUTHENTICATION
# =============================================================================
AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'accounts:login'

# =============================================================================
# INTERNATIONALIZATION
# =============================================================================
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# =============================================================================
# STATIC FILES (CSS, JavaScript, Images)
# =============================================================================
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# =============================================================================
# GOOGLE CLOUD STORAGE - Media Files
# =============================================================================
USE_GCS = config('USE_GCS', default=False, cast=bool)

if USE_GCS:
    # Google Cloud Storage Configuration
    DEFAULT_FILE_STORAGE = 'storages.backends.gcloud.GoogleCloudStorage'
    GS_BUCKET_NAME = config('GCS_BUCKET_NAME')
    GS_PROJECT_ID = config('GCS_PROJECT_ID')
    GS_CREDENTIALS = config('GOOGLE_APPLICATION_CREDENTIALS', default=None)
    GS_DEFAULT_ACL = 'publicRead'
    GS_QUERYSTRING_AUTH = False
    GS_FILE_OVERWRITE = False
    
    # Custom domain for CDN (optional)
    GS_CUSTOM_ENDPOINT = config('GCS_CUSTOM_ENDPOINT', default=None)
    
    MEDIA_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/'
else:
    # Local development
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'

# =============================================================================
# FILE UPLOAD SETTINGS - Para vídeos maiores
# =============================================================================
# Aumenta limites para upload de arquivos grandes (vídeos)
DATA_UPLOAD_MAX_MEMORY_SIZE = 524288000  # 500 MB (em bytes)
FILE_UPLOAD_MAX_MEMORY_SIZE = 524288000  # 500 MB (em bytes)
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000

# =============================================================================
# CRISPY FORMS
# =============================================================================
CRISPY_ALLOWED_TEMPLATE_PACKS = 'tailwind'
CRISPY_TEMPLATE_PACK = 'tailwind'

# =============================================================================
# DEFAULT PRIMARY KEY
# =============================================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================================
# MINDPULSE CUSTOM SETTINGS
# =============================================================================
MINDPULSE_SETTINGS = {
    'BRAND_COLOR': '#F83531',
    'BACKGROUND_COLOR': '#1A1A1A',
    'TEXT_COLOR': '#FFFFFF',
    'MAX_VIDEO_SIZE_MB': 500,
    'ALLOWED_VIDEO_FORMATS': ['mp4', 'webm', 'mov'],
    'DEFAULT_AVATAR': 'avatars/default.png',
}

# =============================================================================
# EMAIL CONFIGURATION (SMTP)
# =============================================================================
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.smtp.EmailBackend'
)

# Configurações básicas SMTP
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

# Configuração TLS/SSL baseada na porta
EMAIL_PORT_INT = int(EMAIL_PORT)
if EMAIL_PORT_INT == 465:
    # Porta 465 requer SSL
    EMAIL_USE_SSL = True
    EMAIL_USE_TLS = False
elif EMAIL_PORT_INT == 587:
    # Porta 587 requer TLS
    EMAIL_USE_TLS = True
    EMAIL_USE_SSL = False
else:
    # Para outras portas, tentar TLS por padrão
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)

# IMPORTANTE: DEFAULT_FROM_EMAIL deve ser igual ou usar o mesmo domínio do EMAIL_HOST_USER
# Muitos provedores (especialmente Gmail) exigem isso para autenticação
if EMAIL_HOST_USER:
    # Se EMAIL_HOST_USER está configurado, usar ele como DEFAULT_FROM_EMAIL
    DEFAULT_FROM_EMAIL = config(
        'DEFAULT_FROM_EMAIL',
        default=f'Mindpulse <{EMAIL_HOST_USER}>'
    )
else:
    DEFAULT_FROM_EMAIL = config(
        'DEFAULT_FROM_EMAIL',
        default='Mindpulse <noreply@mindpulse.com.br>'
    )

SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Configurações de timeout para envio de e-mail
EMAIL_TIMEOUT = 30

# URL base do site (para links em e-mails)
SITE_URL = config('SITE_URL', default='http://localhost:8000')

# Token de reset de senha expira em 24 horas (padrão Django é 3 dias)
PASSWORD_RESET_TIMEOUT = 86400  # 24 horas em segundos

# =============================================================================
# SECURITY SETTINGS (Production)
# =============================================================================
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

