"""
Backend Configuration Manager
Central configuration system for Django backend using soft coding techniques
Manages all settings, paths, and environment configurations
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional

# Load .env file
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / '.env')

class BackendConfig:
    """
    Central configuration class for the Django backend
    Implements soft coding principles for maximum flexibility
    """
    
    def __init__(self, environment: str = None):
        self.environment = environment or os.getenv('DJANGO_ENV', 'development')
        self.base_dir = Path(__file__).resolve().parent.parent
        self._load_configuration()
    
    def _load_configuration(self):
        """Load configuration based on environment"""
        # Base configuration
        self.config = {
            # Project metadata
            'project': {
                'name': 'XERXEZ Backend',
                'description': 'Django REST API backend for XERXEZ frontend',
                'version': '1.0.0',
                'author': 'XERXEZ Team',
                'api_version': 'v1'
            },
            
            # Paths configuration (soft coded)
            'paths': {
                'base': str(self.base_dir),
                'apps': str(self.base_dir / 'apps'),
                'config': str(self.base_dir / 'config'),
                'scripts': str(self.base_dir / 'scripts'),
                'static': str(self.base_dir / 'staticfiles'),
                'media': str(self.base_dir / 'media'),
                'logs': str(self.base_dir / 'logs'),
                'docs': str(self.base_dir / 'docs'),
                'requirements': str(self.base_dir / 'requirements'),
            },
            
  # Database configuration
'database': {
    'default': {
        'engine': 'django.db.backends.postgresql',
        'name': os.getenv('DB_NAME', 'xerxez'),
        'user': os.getenv('DB_USER', 'xerxez_user'),
        'password': os.getenv('DB_PASSWORD', 'xerxez_pass'),
        'host': os.getenv('DB_HOST', 'postgres'),
        'port': os.getenv('DB_PORT', '5432'),
        'options': {
            'sslmode': os.getenv('DB_SSLMODE', 'prefer'),
        }
    },
    'backup': {
        'enabled': True,
        'schedule': '0 2 * * *',  # Daily at 2 AM
        'retention_days': 30
    }
},         
            # API configuration
            'api': {
                'prefix': 'api',
                'version': 'v1',
                'documentation': {
                    'enabled': True,
                    'title': 'XERXEZ API Documentation',
                    'description': 'REST API for XERXEZ SEO & Digital Marketing Platform'
                },
                'cors': {
                    'allowed_origins': self._get_cors_origins(),
                    'allow_credentials': True,
                    'max_age': 3600
                },
                'rate_limiting': {
                    'enabled': True,
                    'default_rate': '1000/hour',
                    'auth_rate': '10000/hour'
                }
            },
            
            # Security configuration
            'security': {
                'secret_key': os.getenv('DJANGO_SECRET_KEY', self._generate_secret_key()),
                'allowed_hosts': self._get_allowed_hosts(),
                'csrf': {
                    'trusted_origins': self._get_trusted_origins(),
                },
                'session': {
                    'cookie_secure': self.environment == 'production',
                    'cookie_httponly': True,
                    'cookie_samesite': 'Lax'
                }
            },
            
            # Application modules
            'apps': {
                'core': {
                    'enabled': True,
                    'path': 'apps.core'
                },
                'authentication': {
                    'enabled': True,
                    'path': 'apps.authentication'
                },
                'users': {
                    'enabled': True,
                    'path': 'apps.users'
                },
                'blog': {
                    'enabled': True,
                    'path': 'apps.blog'
                },
                'services': {
                    'enabled': True,
                    'path': 'apps.services'
                },
                'projects': {
                    'enabled': True,
                    'path': 'apps.projects'
                },
                'contact': {
                    'enabled': True,
                    'path': 'apps.contact'
                },
                'analytics': {
                    'enabled': True,
                    'path': 'apps.analytics'
                },
                # ---- ERP modules ----
                'crm': {
                    'enabled': True,
                    'path': 'apps.crm'
                },
                'sales': {
                    'enabled': True,
                    'path': 'apps.sales'
                },
                'invoicing': {
                    'enabled': True,
                    'path': 'apps.invoicing'
                },
                'hr': {
                    'enabled': True,
                    'path': 'apps.hr'
                },
                'inventory': {
                    'enabled': True,
                    'path': 'apps.inventory'
                },
                'accounting': {
                    'enabled': True,
                    'path': 'apps.accounting'
                },
                'tickets': {
                    'enabled': True,
                    'path': 'apps.tickets'
                }
            },
            
            # Third-party integrations
            'integrations': {
                'email': {
                    'backend': 'django.core.mail.backends.smtp.EmailBackend',
                    'host': os.getenv('EMAIL_HOST', 'smtp.gmail.com'),
                    'port': int(os.getenv('EMAIL_PORT', '587')),
                    'use_tls': True,
                    'user': os.getenv('EMAIL_USER', ''),
                    'password': os.getenv('EMAIL_PASSWORD', '')
                },
                'storage': {
                    'backend': os.getenv('STORAGE_BACKEND', 'local'),
                    'aws_s3': {
                        'bucket': os.getenv('AWS_S3_BUCKET', ''),
                        'region': os.getenv('AWS_S3_REGION', 'us-east-1'),
                        'access_key': os.getenv('AWS_ACCESS_KEY_ID', ''),
                        'secret_key': os.getenv('AWS_SECRET_ACCESS_KEY', '')
                    }
                },
                'cache': {
                    'backend': 'django.core.cache.backends.redis.RedisCache' if self.environment == 'production' 
                             else 'django.core.cache.backends.locmem.LocMemCache',
                    'location': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
                    'timeout': 300,
                    'options': {}
                }
            },
            
            # Development settings
            'development': {
                'debug': True,
                'auto_reload': True,
                'show_toolbar': False,
                'log_level': 'DEBUG',
                'profiling': False
            },
            
            # Production settings
            'production': {
                'debug': False,
                'auto_reload': False,
                'show_toolbar': False,
                'log_level': 'WARNING',
                'profiling': False,
                'ssl_redirect': True,
                'secure_proxy_ssl_header': ('HTTP_X_FORWARDED_PROTO', 'https')
            },
            
            # Logging configuration
            'logging': {
                'version': 1,
                'disable_existing_loggers': False,
                'formatters': {
                    'verbose': {
                        'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
                        'style': '{',
                    },
                    'simple': {
                        'format': '{levelname} {message}',
                        'style': '{',
                    },
                },
                'handlers': {
                    
                    'console': {
                        'level': 'DEBUG',
                        'class': 'logging.StreamHandler',
                        'formatter': 'simple',
                    },
                },
                'root': {
                    'handlers': ['console'],
                    'level': 'WARNING',
                },
            }
        }
    
    def _get_cors_origins(self) -> List[str]:
        """Get CORS allowed origins based on environment"""
        env_value = os.getenv('CORS_ALLOWED_ORIGINS')
        if env_value:
            return [o.strip() for o in env_value.split(',') if o.strip()]
        if self.environment == 'production':
            return [
                'https://xerxez-frontend.com',
                'https://www.xerxez-frontend.com',
            ]
        return [
            'http://localhost:5173',  # Vite dev server
            'http://127.0.0.1:5173',
            'http://localhost:3000',  # Alternative frontend
            'http://127.0.0.1:3000',
        ]
    
    def _get_allowed_hosts(self) -> List[str]:
        """Get allowed hosts based on environment"""
        env_value = os.getenv('ALLOWED_HOSTS')
        if env_value:
            return [h.strip() for h in env_value.split(',') if h.strip()]
        if self.environment == 'production':
            return [
                'api.xerxez-frontend.com',
                'backend.xerxez-frontend.com',
                '.xerxez-frontend.com',
                '.up.railway.app',
            ]
        return ['localhost', 'localhost:8000', '127.0.0.1', '127.0.0.1:8000', '[::1]', 'xerxez-backend']
    
    def _get_trusted_origins(self) -> List[str]:
        """Get CSRF trusted origins"""
        env_value = os.getenv('CSRF_TRUSTED_ORIGINS')
        if env_value:
            return [o.strip() for o in env_value.split(',') if o.strip()]
        if self.environment == 'production':
            return [
                'https://xerxez-frontend.com',
                'https://www.xerxez-frontend.com',
            ]
        return [
            'http://localhost:5173',
            'http://127.0.0.1:5173',
        ]
    
    def _generate_secret_key(self) -> str:
        """Generate a secret key if not provided"""
        from django.core.management.utils import get_random_secret_key
        return get_random_secret_key()
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        Example: config.get('database.default.name')
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any) -> None:
        """
        Set configuration value using dot notation
        Example: config.set('database.default.name', 'new_db_name')
        """
        keys = key_path.split('.')
        config = self.config
        
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        config[keys[-1]] = value
    
    def get_database_url(self) -> str:
        """Get PostgreSQL database URL"""
        db_config = self.get('database.default')
        return (f"postgresql://{db_config['user']}:{db_config['password']}"
                f"@{db_config['host']}:{db_config['port']}/{db_config['name']}")
    
    def get_enabled_apps(self) -> List[str]:
        """Get list of enabled Django apps"""
        apps = []
        for app_name, app_config in self.get('apps', {}).items():
            if app_config.get('enabled', False):
                apps.append(app_config['path'])
        return apps
    
    def is_debug_enabled(self) -> bool:
        """Check if debug mode is enabled"""
        return self.get(f'{self.environment}.debug', False)
    
    def export_environment_variables(self) -> Dict[str, str]:
        """Export configuration as environment variables"""
        env_vars = {}
        
        # Database
        db = self.get('database.default')
        env_vars.update({
            'DB_NAME': db['name'],
            'DB_USER': db['user'],
            'DB_PASSWORD': db['password'],
            'DB_HOST': db['host'],
            'DB_PORT': str(db['port']),
        })
        
        # Security
        security = self.get('security')
        env_vars['DJANGO_SECRET_KEY'] = security['secret_key']
        
        # Environment
        env_vars['DJANGO_ENV'] = self.environment
        
        return env_vars

# Global configuration instance
backend_config = BackendConfig()