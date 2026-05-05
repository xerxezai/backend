"""
Django settings for SEOZ Backend
Uses soft coding configuration for maximum flexibility
"""

import os
import sys
from pathlib import Path

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Add the config directory to Python path
sys.path.insert(0, os.path.join(BASE_DIR, 'config'))

# Import our soft-coded configuration
from backend_config import backend_config

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = backend_config.get('security.secret_key')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = backend_config.is_debug_enabled()

ALLOWED_HOSTS = backend_config.get('security.allowed_hosts')

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'drf_yasg',  # API documentation
    'django_filters',
    'django_extensions',
]

LOCAL_APPS = backend_config.get_enabled_apps()

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'seoz_backend.urls'

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

WSGI_APPLICATION = 'seoz_backend.wsgi.application'

# Database configuration using soft coding
DATABASES = {
    'default': {
        'ENGINE': backend_config.get('database.default.engine'),
        'NAME': backend_config.get('database.default.name'),
        'USER': backend_config.get('database.default.user'),
        'PASSWORD': backend_config.get('database.default.password'),
        'HOST': backend_config.get('database.default.host'),
        'PORT': backend_config.get('database.default.port'),
        'OPTIONS': backend_config.get('database.default.options', {}),
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = backend_config.get('paths.static')

# No additional static files directories since this is API-only
# STATICFILES_DIRS = []

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = backend_config.get('paths.media')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': backend_config.get('api.rate_limiting.default_rate'),
        'user': backend_config.get('api.rate_limiting.auth_rate')
    }
}

# CORS configuration
CORS_ALLOWED_ORIGINS = backend_config.get('api.cors.allowed_origins')
CORS_ALLOW_CREDENTIALS = backend_config.get('api.cors.allow_credentials')
CORS_PREFLIGHT_MAX_AGE = backend_config.get('api.cors.max_age')

# CSRF configuration
CSRF_TRUSTED_ORIGINS = backend_config.get('security.csrf.trusted_origins')

# Session configuration
SESSION_COOKIE_SECURE = backend_config.get('security.session.cookie_secure')
SESSION_COOKIE_HTTPONLY = backend_config.get('security.session.cookie_httponly')
SESSION_COOKIE_SAMESITE = backend_config.get('security.session.cookie_samesite')

# Email configuration
EMAIL_BACKEND = backend_config.get('integrations.email.backend')
EMAIL_HOST = backend_config.get('integrations.email.host')
EMAIL_PORT = backend_config.get('integrations.email.port')
EMAIL_USE_TLS = backend_config.get('integrations.email.use_tls')
EMAIL_HOST_USER = backend_config.get('integrations.email.user')
EMAIL_HOST_PASSWORD = backend_config.get('integrations.email.password')

# Cache configuration
CACHES = {
    'default': {
        'BACKEND': backend_config.get('integrations.cache.backend'),
        'LOCATION': backend_config.get('integrations.cache.location'),
        'TIMEOUT': backend_config.get('integrations.cache.timeout'),
        'OPTIONS': backend_config.get('integrations.cache.options', {}),
    }
}

# Logging configuration
LOGGING = backend_config.get('logging')

# API Documentation (Swagger)
SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'Token': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header'
        }
    },
    'USE_SESSION_AUTH': False,
    'JSON_EDITOR': True,
    'SUPPORTED_SUBMIT_METHODS': [
        'get',
        'post',
        'put',
        'delete',
        'patch'
    ],
    'OPERATIONS_SORTER': 'alpha',
    'TAGS_SORTER': 'alpha',
    'DOC_EXPANSION': 'none',
    'DEEP_LINKING': True,
    'SHOW_EXTENSIONS': True,
    'SHOW_COMMON_EXTENSIONS': True,
}

REDOC_SETTINGS = {
    'LAZY_RENDERING': False,
    'HIDE_HOSTNAME': False,
    'EXPAND_RESPONSES': [200, 201],
}

# Production-specific settings
if not DEBUG:
    # Security settings for production
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_HSTS_SECONDS = 3600
    
    if backend_config.get('production.ssl_redirect'):
        SECURE_SSL_REDIRECT = True
        SECURE_PROXY_SSL_HEADER = backend_config.get('production.secure_proxy_ssl_header')

# Development-specific settings
if DEBUG:
    # Development tools
    if backend_config.get('development.show_toolbar'):
        INSTALLED_APPS += ['debug_toolbar']
        MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE
        
    INTERNAL_IPS = [
        '127.0.0.1',
        'localhost',
    ]
    
    # Development database might use SQLite for simplicity
    if os.getenv('USE_SQLITE', 'False').lower() == 'true':
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }