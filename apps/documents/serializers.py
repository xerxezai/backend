from rest_framework import serializers

from .models import Document, DocumentVersion


class DocumentVersionSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True, default='')
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = DocumentVersion
        fields = ['id', 'document', 'version_number', 'file', 'file_url', 'uploaded_by', 'uploaded_by_name', 'notes', 'created_at']
        read_only_fields = ['id', 'document', 'uploaded_by', 'created_at']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if not obj.file:
            return None
        return request.build_absolute_uri(obj.file.url) if request else obj.file.url


class DocumentSerializer(serializers.ModelSerializer):
    """Full serializer — detail view, create, update."""
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True, default='')
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True, default='')
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display   = serializers.CharField(source='get_status_display', read_only=True)
    file_url         = serializers.SerializerMethodField()
    versions         = DocumentVersionSerializer(many=True, read_only=True)

    class Meta:
        model = Document
        fields = [
            'id', 'title', 'description', 'category', 'category_display', 'file', 'file_url',
            'version', 'status', 'status_display', 'uploaded_by', 'uploaded_by_name',
            'approved_by', 'approved_by_name', 'created_at', 'updated_at', 'versions',
        ]
        # status only changes via the approve/reject actions, never a direct PUT/PATCH —
        # keeps "who approved it" (approved_by) trustworthy.
        read_only_fields = ['id', 'status', 'uploaded_by', 'approved_by', 'created_at', 'updated_at']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if not obj.file:
            return None
        return request.build_absolute_uri(obj.file.url) if request else obj.file.url


class DocumentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for the list view — drops the long-form description."""
    uploaded_by_name  = serializers.CharField(source='uploaded_by.username', read_only=True, default='')
    category_display  = serializers.CharField(source='get_category_display', read_only=True)
    status_display    = serializers.CharField(source='get_status_display', read_only=True)
    file_url          = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'id', 'title', 'category', 'category_display', 'file_url', 'version', 'status',
            'status_display', 'uploaded_by', 'uploaded_by_name', 'created_at', 'updated_at',
        ]

    def get_file_url(self, obj):
        request = self.context.get('request')
        if not obj.file:
            return None
        return request.build_absolute_uri(obj.file.url) if request else obj.file.url
