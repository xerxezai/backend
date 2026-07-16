from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated

from .models import Document, DocumentVersion
from .serializers import DocumentSerializer, DocumentListSerializer, DocumentVersionSerializer


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_class(self):
        if self.action == 'list':
            return DocumentListSerializer
        return DocumentSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def get_queryset(self):
        qs = super().get_queryset()
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        document = self.get_object()
        document.status = 'approved'
        document.approved_by = request.user
        document.save(update_fields=['status', 'approved_by', 'updated_at'])
        return Response(DocumentSerializer(document, context=self.get_serializer_context()).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        document = self.get_object()
        document.status = 'rejected'
        document.approved_by = request.user
        document.save(update_fields=['status', 'approved_by', 'updated_at'])
        return Response(DocumentSerializer(document, context=self.get_serializer_context()).data)

    @action(detail=True, methods=['get'])
    def versions(self, request, pk=None):
        document = self.get_object()
        qs = document.versions.all()
        serializer = DocumentVersionSerializer(qs, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='upload_version')
    def upload_version(self, request, pk=None):
        document = self.get_object()
        serializer = DocumentVersionSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        version = serializer.save(document=document, uploaded_by=request.user)

        # Keep the parent Document's own file/version fields pointing at the latest
        # upload so every other view (list, cards, detail) reflects it without a join.
        document.file = version.file
        document.version = version.version_number
        document.status = 'draft'
        document.save(update_fields=['file', 'version', 'status', 'updated_at'])

        return Response(DocumentVersionSerializer(version, context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def search(self, request):
        q = request.query_params.get('q', '').strip()
        category = request.query_params.get('category', '').strip()
        qs = self.get_queryset()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
        if category:
            qs = qs.filter(category=category)
        serializer = DocumentListSerializer(qs, many=True, context=self.get_serializer_context())
        return Response(serializer.data)
