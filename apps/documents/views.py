import logging
import secrets

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings as django_settings
from django.db.models import F, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.companies.mixins import CompanyScopedMixin
from .models import Document, DocumentVersion, DocumentComment, DocumentAuditTrail
from .serializers import (
    DocumentSerializer, DocumentListSerializer, DocumentVersionSerializer,
    DocumentCommentSerializer, DocumentAuditTrailSerializer,
)

logger = logging.getLogger(__name__)


def _send_safe(subject, message, recipient_list):
    """send_mail wrapped so email failures never break the main request (matches
    apps.lma.views._send_safe's pattern) — uses the same EMAIL_HOST config as
    every other transactional email in this project."""
    recipient_list = [r for r in recipient_list if r]
    if not recipient_list:
        return
    try:
        from_email = getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'xerxez.in@gmail.com')
        send_mail(subject, message, from_email, recipient_list, fail_silently=True)
    except Exception as exc:
        logger.warning('Document email failed: %s', exc)


class DocumentViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = Document.objects.filter(is_deleted=False)
    serializer_class = DocumentSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        # The shared-link download is the one public, no-auth endpoint on this viewset.
        if self.action == 'shared':
            return [AllowAny()]
        return super().get_permissions()

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
        return self.company_scope(qs)

    def _log(self, document, action_name, notes=''):
        user = self.request.user if self.request.user.is_authenticated else None
        DocumentAuditTrail.objects.create(document=document, user=user, action=action_name, notes=notes)

    # ── create / retrieve / update / delete ──────────────────────────────────

    def perform_create(self, serializer):
        company, _ = self._company_context()
        document = serializer.save(uploaded_by=self.request.user, company=company)
        self._log(document, 'uploaded')

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        Document.objects.filter(pk=instance.pk).update(views_count=F('views_count') + 1)
        instance.refresh_from_db(fields=['views_count'])
        self._log(instance, 'viewed')
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def perform_update(self, serializer):
        document = serializer.save()
        self._log(document, 'edited')

    def perform_destroy(self, instance):
        # Soft delete — keeps the row (and its audit trail) around instead of removing it.
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted'])
        self._log(instance, 'deleted')

    @action(detail=True, methods=['post'], url_path='track-download')
    def track_download(self, request, pk=None):
        """The frontend downloads the file directly from its media URL (not through this
        API), so it calls this endpoint alongside that to get a 'downloaded' audit entry."""
        document = self.get_object()
        self._log(document, 'downloaded')
        return Response({'status': 'logged'})

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        document = self.get_object()
        document.status = 'approved'
        document.approved_by = request.user
        document.save(update_fields=['status', 'approved_by', 'updated_at'])
        self._log(document, 'approved')
        if document.uploaded_by and document.uploaded_by.email:
            _send_safe(
                f'Document approved: {document.title}',
                f'Your document "{document.title}" has been approved in XERXEZ ERP. '
                f'Login to view: xerxez.com/erp',
                [document.uploaded_by.email],
            )
        return Response(DocumentSerializer(document, context=self.get_serializer_context()).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        document = self.get_object()
        document.status = 'rejected'
        document.approved_by = request.user
        document.save(update_fields=['status', 'approved_by', 'updated_at'])
        self._log(document, 'rejected')
        if document.uploaded_by and document.uploaded_by.email:
            _send_safe(
                f'Document rejected: {document.title}',
                f'Your document "{document.title}" was rejected in XERXEZ ERP. '
                f'Login to review: xerxez.com/erp',
                [document.uploaded_by.email],
            )
        return Response(DocumentSerializer(document, context=self.get_serializer_context()).data)

    @action(detail=True, methods=['post'], url_path='submit-for-review')
    def submit_for_review(self, request, pk=None):
        """Moves a draft document into the approval queue and notifies admins —
        the only path that sets status='under_review'."""
        document = self.get_object()
        document.status = 'under_review'
        document.save(update_fields=['status', 'updated_at'])
        self._log(document, 'edited', notes='Submitted for review')
        User = get_user_model()
        admin_emails = list(User.objects.filter(is_staff=True, is_active=True).exclude(email='').values_list('email', flat=True))
        _send_safe(
            f'Document Pending Approval: {document.title}',
            'A document needs your approval in XERXEZ ERP. Login to review: xerxez.com/erp',
            admin_emails,
        )
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
        version = serializer.save(document=document, uploaded_by=request.user, company=document.company)

        # Keep the parent Document's own file/version fields pointing at the latest
        # upload so every other view (list, cards, detail) reflects it without a join.
        document.file = version.file
        document.version = version.version_number
        document.status = 'draft'
        document.save(update_fields=['file', 'version', 'status', 'updated_at'])
        self._log(document, 'new_version', notes=version.version_number)

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

    # ── comments ──────────────────────────────────────────────────────────────

    @action(detail=True, methods=['get', 'post'], url_path='comments')
    def comments(self, request, pk=None):
        document = self.get_object()
        if request.method == 'POST':
            serializer = DocumentCommentSerializer(data=request.data, context=self.get_serializer_context())
            serializer.is_valid(raise_exception=True)
            comment = serializer.save(document=document, user=request.user, company=document.company)
            self._log(document, 'commented', notes=comment.comment[:200])
            return Response(DocumentCommentSerializer(comment, context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED)
        qs = document.comments.select_related('user').all()
        return Response(DocumentCommentSerializer(qs, many=True, context=self.get_serializer_context()).data)

    @action(detail=True, methods=['delete'], url_path='comments/(?P<comment_id>[^/.]+)')
    def delete_comment(self, request, pk=None, comment_id=None):
        document = self.get_object()
        comment = get_object_or_404(DocumentComment, pk=comment_id, document=document)
        comment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── audit trail ───────────────────────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='audit-trail')
    def audit_trail(self, request, pk=None):
        document = self.get_object()
        qs = document.audit_trail.select_related('user').all()
        return Response(DocumentAuditTrailSerializer(qs, many=True, context=self.get_serializer_context()).data)

    # ── sharing ───────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='generate-share-link')
    def generate_share_link(self, request, pk=None):
        document = self.get_object()
        if not document.share_token:
            document.share_token = secrets.token_urlsafe(16)
            document.save(update_fields=['share_token'])
        self._log(document, 'shared')
        share_url = request.build_absolute_uri(f'/api/v1/documents/shared/{document.share_token}/')
        return Response({'share_token': document.share_token, 'share_url': share_url})

    @action(detail=False, methods=['get'], url_path='shared/(?P<token>[^/.]+)')
    def shared(self, request, token=None):
        """Public, unauthenticated download link. Redirects straight to the file so it
        works as a plain URL pasted anywhere, with no API client needed."""
        document = Document.objects.filter(share_token=token, is_deleted=False).first()
        if not document or not document.file:
            return Response({'detail': 'Invalid or expired share link.'}, status=status.HTTP_404_NOT_FOUND)
        DocumentAuditTrail.objects.create(document=document, user=None, action='downloaded', notes='via share link')
        return HttpResponseRedirect(document.file.url)
