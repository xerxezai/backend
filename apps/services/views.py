from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from .models import Service
from .serializers import ServiceSerializer


class ServiceViewSet(ModelViewSet):
    """
    Public can READ services (GET).
    Only authenticated users can CREATE/UPDATE/DELETE.
    """
    queryset = Service.objects.filter(is_published=True)
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]