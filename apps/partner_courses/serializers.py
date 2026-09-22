from rest_framework import serializers
from .models import PartnerCourse


class PartnerCoursePublicSerializer(serializers.ModelSerializer):
    """Active-course view for the public Training page. affiliate_code is
    intentionally included here — it doubles as the customer-facing coupon
    code shown in the pre-redirect modal ("Use coupon code: XERXEZ20 for
    20% off"), not just an internal tracking value."""
    partner_logo = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = PartnerCourse
        fields = [
            'id', 'partner_name', 'partner_logo', 'partner_website',
            'title', 'description', 'category', 'level', 'duration', 'price',
            'thumbnail', 'affiliate_link', 'affiliate_code', 'is_featured', 'order',
        ]

    def _absolute(self, field):
        if not field:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(field.url) if request else field.url

    def get_partner_logo(self, obj):
        return self._absolute(obj.partner_logo)

    def get_thumbnail(self, obj):
        return self._absolute(obj.thumbnail)


class PartnerCourseSerializer(serializers.ModelSerializer):
    """Full read/write serializer — admin only."""
    partner_logo = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = PartnerCourse
        fields = [
            'id', 'partner_name', 'partner_logo', 'partner_website',
            'title', 'description', 'category', 'level', 'duration', 'price',
            'thumbnail', 'affiliate_link', 'affiliate_code',
            'is_active', 'is_featured', 'order', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _absolute(self, field):
        if not field:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(field.url) if request else field.url

    def get_partner_logo(self, obj):
        return self._absolute(obj.partner_logo)

    def get_thumbnail(self, obj):
        return self._absolute(obj.thumbnail)


class PartnerCourseWriteSerializer(serializers.ModelSerializer):
    """Used for create/update — accepts multipart file uploads directly for
    partner_logo/thumbnail, unlike the read serializers above which convert
    them to absolute URLs for display."""
    class Meta:
        model = PartnerCourse
        fields = [
            'partner_name', 'partner_logo', 'partner_website',
            'title', 'description', 'category', 'level', 'duration', 'price',
            'thumbnail', 'affiliate_link', 'affiliate_code',
            'is_active', 'is_featured', 'order',
        ]
