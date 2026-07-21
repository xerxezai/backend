"""
URL configuration for XERXEZ Backend
Uses soft coding approach for flexible API routing
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
import sys
import os

# Add config to path
sys.path.insert(0, os.path.join(settings.BASE_DIR, 'config'))
from backend_config import backend_config


# Swagger configuration
schema_view = get_schema_view(
    openapi.Info(
        title=backend_config.get('api.documentation.title'),
        default_version=backend_config.get('api.version'),
        description=backend_config.get('api.documentation.description'),
        contact=openapi.Contact(email="admin@xerxez.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    url='https://backend-production-b9f2.up.railway.app',
)


# API URL patterns
api_patterns = [
    path('auth/', include('apps.authentication.urls')),
    path('users/', include('apps.users.urls')),
    path('blog/', include('apps.blog.urls')),
    path('services/', include('apps.services.urls')),
    path('projects/', include('apps.projects.urls')),
    path('contact/', include('apps.contact.urls')),
    path('careers/', include('apps.careers.urls')),
    path('documents/', include('apps.documents.urls')),
    path('analytics/', include('apps.analytics.urls')),
    path('chat/', include('apps.chatbot.urls')),
    path('core/', include('apps.core.urls', namespace='core-api')),

    # ERP modules
    path('crm/', include('apps.crm.urls')),
    path('sales/', include('apps.sales.urls')),
    path('invoicing/', include('apps.invoicing.urls')),
    path('hr/', include('apps.hr.urls')),
    path('inventory/', include('apps.inventory.urls')),
    path('accounting/', include('apps.accounting.urls')),
    path('tickets/', include('apps.tickets.urls')),

    path('purchases/', include('apps.purchases.urls')),
    path('procurement/', include('apps.procurement.urls')),
    path('logistics/', include('apps.logistics.urls')),
    path('reports/', include('apps.reports.urls')),

    # MLM module
    path('mlm/', include('apps.mlm.urls')),

    # LMA module
    path('lma/', include('apps.lma.urls')),

    # EPC modules — note: 'project-management/' (not 'projects/', which apps.projects
    # already owns for the marketing site's portfolio/case-studies pages).
    path('project-management/', include('apps.project_management.urls')),
    path('asset-management/', include('apps.asset_management.urls')),
    path('qhse/', include('apps.qhse.urls')),

    # RBAC — mounted at 'rbac/' (making the real path /api/v1/rbac/...) to match this
    # codebase's single /api/v1/ prefix convention, not the standalone 'api/rbac/' path
    # given in the original spec.
    path('rbac/', include('apps.rbac.urls')),

    # Multi-tenant companies — mounted under /api/v1/ (not the spec's standalone 'api/')
    # for the same reason.
    path('', include('apps.companies.urls')),

    # Partner applications — mounted under /api/v1/ (not the spec's standalone
    # '/api/partners/') to match this codebase's single-prefix convention.
    path('partners/', include('apps.partners.urls')),
]


# Root endpoint
def api_root(request):
    return JsonResponse({
        "message": "XERXEZ Backend is running",
        "docs": "/docs/",
        "redoc": "/redoc/",
        "api": f"/{backend_config.get('api.prefix')}/{backend_config.get('api.version')}/",
        "health": "/health/"
    })


urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # API
    path(
        f"{backend_config.get('api.prefix')}/{backend_config.get('api.version')}/",
        include(api_patterns)
    ),

    # Documentation
    path(
        'docs/',
        schema_view.with_ui('swagger', cache_timeout=0),
        name='schema-swagger-ui'
    ),

    path(
        'redoc/',
        schema_view.with_ui('redoc', cache_timeout=0),
        name='schema-redoc'
    ),

    path(
        'api-docs.json',
        schema_view.without_ui(cache_timeout=0),
        name='schema-json'
    ),

    # Health check
    path('health/', include('apps.core.urls', namespace='core-health')),

    # Root endpoint
    path('', api_root),
]


# Debug toolbar
if settings.DEBUG and 'debug_toolbar' in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns


# Serve static and media files
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )

    urlpatterns += static(
        settings.STATIC_URL,
        document_root=settings.STATIC_ROOT
    )


# Error handlers
handler404 = 'apps.core.views.handler404'
handler500 = 'apps.core.views.handler500'