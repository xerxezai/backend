from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from .models import PartnerCourse
from .serializers import (
    PartnerCoursePublicSerializer, PartnerCourseSerializer, PartnerCourseWriteSerializer,
)


class IsStaffUser(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff)


@api_view(['GET'])
@permission_classes([AllowAny])
def list_partner_courses(request):
    """GET /api/v1/partner-courses/ — public, active courses only.
    Optional filters: ?category=, ?partner=, ?level="""
    courses = PartnerCourse.objects.filter(is_active=True)

    category = request.GET.get('category')
    if category and category.lower() != 'all':
        courses = courses.filter(category__iexact=category)

    partner = request.GET.get('partner')
    if partner:
        courses = courses.filter(partner_name__iexact=partner)

    level = request.GET.get('level')
    if level:
        courses = courses.filter(level__iexact=level)

    return Response(PartnerCoursePublicSerializer(courses, many=True, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([IsStaffUser])
def admin_list_partner_courses(request):
    """GET /api/v1/partner-courses/admin/ — every course, active or not."""
    courses = PartnerCourse.objects.all()
    return Response(PartnerCourseSerializer(courses, many=True, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([IsStaffUser])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def create_partner_course(request):
    """POST /api/v1/partner-courses/admin/create/"""
    serializer = PartnerCourseWriteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    course = serializer.save()
    return Response(PartnerCourseSerializer(course, context={'request': request}).data, status=201)


@api_view(['PUT', 'DELETE'])
@permission_classes([IsStaffUser])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def update_partner_course(request, course_id):
    """PUT/DELETE /api/v1/partner-courses/admin/<id>/"""
    try:
        course = PartnerCourse.objects.get(id=course_id)
    except PartnerCourse.DoesNotExist:
        return Response({'error': 'Partner course not found.'}, status=404)

    if request.method == 'DELETE':
        course.delete()
        return Response(status=204)

    serializer = PartnerCourseWriteSerializer(course, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    course = serializer.save()
    return Response(PartnerCourseSerializer(course, context={'request': request}).data)
