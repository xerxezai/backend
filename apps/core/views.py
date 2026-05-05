"""
Core views for SEOZ Backend
Provides base functionality and health checks
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.http import JsonResponse
from django.db import connection
from django.conf import settings
from django.utils import timezone
import sys
import os

# Add config to path
sys.path.insert(0, os.path.join(settings.BASE_DIR, 'config'))
from backend_config import backend_config


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint for monitoring
    """
    try:
        # Check database connection
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            db_status = 'healthy'
    except Exception as e:
        db_status = f'unhealthy: {str(e)}'
    
    health_data = {
        'status': 'healthy' if db_status == 'healthy' else 'unhealthy',
        'timestamp': timezone.now().isoformat(),
        'version': backend_config.get('project.version'),
        'environment': backend_config.environment,
        'database': db_status,
        'debug': settings.DEBUG,
        'api_version': backend_config.get('api.version'),
    }
    
    status_code = status.HTTP_200_OK if health_data['status'] == 'healthy' else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(health_data, status=status_code)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_root(request):
    """
    API root endpoint providing available endpoints
    """
    return Response({
        'message': 'Welcome to SEOZ API',
        'version': backend_config.get('api.version'),
        'documentation': {
            'swagger': request.build_absolute_uri('/docs/'),
            'redoc': request.build_absolute_uri('/redoc/'),
        },
        'endpoints': {
            'health': request.build_absolute_uri('/health/'),
            'auth': request.build_absolute_uri('/api/v1/auth/'),
            'users': request.build_absolute_uri('/api/v1/users/'),
            'blog': request.build_absolute_uri('/api/v1/blog/'),
            'services': request.build_absolute_uri('/api/v1/services/'),
            'projects': request.build_absolute_uri('/api/v1/projects/'),
            'contact': request.build_absolute_uri('/api/v1/contact/'),
            'analytics': request.build_absolute_uri('/api/v1/analytics/'),
        }
    })


def handler404(request, exception):
    """
    Custom 404 handler
    """
    return JsonResponse({
        'error': 'Not Found',
        'message': 'The requested resource was not found.',
        'status_code': 404
    }, status=404)


def handler500(request):
    """
    Custom 500 handler
    """
    return JsonResponse({
        'error': 'Internal Server Error',
        'message': 'An unexpected error occurred. Please try again later.',
        'status_code': 500
    }, status=500)