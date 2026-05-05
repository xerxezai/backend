"""
URL configuration for SEOZ Backend
Uses soft coding approach for flexible API routing
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
import sys
import os

# Add config to path
sys.path.insert(0, os.path.join(settings.BASE_DIR, 'config'))
from backend_config import backend_config

# API Documentation setup
schema_view = get_schema_view(
    openapi.Info(
        title=backend_config.get('api.documentation.title'),
        default_version=backend_config.get('api.version'),
        description=backend_config.get('api.documentation.description'),
        contact=openapi.Contact(email="admin@seoz.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

# API URL patterns
api_patterns = [
    path('auth/', include('apps.authentication.urls')),
    path('users/', include('apps.users.urls')),
    path('blog/', include('apps.blog.urls')),
    path('services/', include('apps.services.urls')),
    path('projects/', include('apps.projects.urls')),
    path('contact/', include('apps.contact.urls')),
    path('analytics/', include('apps.analytics.urls')),
    path('core/', include('apps.core.urls')),
]

urlpatterns = [
    # Admin interface
    path('admin/', admin.site.urls),
    
    # API routes
    path(f"{backend_config.get('api.prefix')}/{backend_config.get('api.version')}/", 
         include(api_patterns)),
    
    # API Documentation
    path('docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('api-docs.json', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    
    # Health check endpoint
    path('health/', include('apps.core.urls')),
    
    # Root API endpoint
    path('', TemplateView.as_view(template_name='api_root.html'), name='api-root'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Debug toolbar
    if 'debug_toolbar' in settings.INSTALLED_APPS:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns

# Custom error handlers
handler404 = 'apps.core.views.handler404'
handler500 = 'apps.core.views.handler500'