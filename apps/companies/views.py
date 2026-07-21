from django.contrib.auth import get_user_model
from django.utils.text import slugify
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.rbac.models import Module, UserModuleAccess
from .models import Company, CompanyUser
from .serializers import CompanySerializer, CompanyUserSerializer
from .utils import resolve_company, get_user_company_role

User = get_user_model()


def _unique_slug(name):
    base = slugify(name) or 'company'
    slug = base
    n = 1
    while Company.objects.filter(slug=slug).exists():
        n += 1
        slug = f'{base}-{n}'
    return slug


class CompanyListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _, is_platform_admin = resolve_company(request)
        if not is_platform_admin:
            return Response({'error': 'Not authorized'}, status=403)
        companies = Company.objects.all()
        return Response(CompanySerializer(companies, many=True).data)

    def post(self, request):
        _, is_platform_admin = resolve_company(request)
        if not is_platform_admin:
            return Response({'error': 'Not authorized'}, status=403)
        data = request.data.copy()
        if not data.get('slug'):
            data['slug'] = _unique_slug(data.get('name', ''))
        serializer = CompanySerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class CompanyDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, company_id):
        _, is_platform_admin = resolve_company(request)
        if not is_platform_admin:
            return Response({'error': 'Not authorized'}, status=403)
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        return Response(CompanySerializer(company).data)

    def put(self, request, company_id):
        _, is_platform_admin = resolve_company(request)
        if not is_platform_admin:
            return Response({'error': 'Not authorized'}, status=403)
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        serializer = CompanySerializer(company, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, company_id):
        _, is_platform_admin = resolve_company(request)
        if not is_platform_admin:
            return Response({'error': 'Not authorized'}, status=403)
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        company.status = 'inactive'
        company.save(update_fields=['status'])
        return Response({'message': 'Company deactivated'})


# Modules a Company Admin is auto-granted across, mirroring how rbac's
# UserManagementView.post() auto-grants a super_admin every module.
ALL_MODULE_NAMES = [c[0] for c in Module.MODULE_CHOICES]


class CompanyUsersView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, company_id):
        _, is_platform_admin = resolve_company(request)
        if not is_platform_admin:
            return Response({'error': 'Not authorized'}, status=403)
        users = CompanyUser.objects.select_related('user').filter(company_id=company_id)
        return Response(CompanyUserSerializer(users, many=True).data)

    def post(self, request, company_id):
        """Add user to company — creates the login account, the CompanyUser
        membership, and (mirroring apps.rbac.views.UserManagementView.post())
        the per-module UserModuleAccess rows so the existing RBAC/data-
        isolation layer immediately recognizes this user's role."""
        _, is_platform_admin = resolve_company(request)
        if not is_platform_admin:
            return Response({'error': 'Not authorized'}, status=403)
        if request.data.get('role') == 'super_admin':
            return Response(
                {'error': 'Super Admin cannot be created through this endpoint. Use the Django admin panel instead.'},
                status=403,
            )
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        data = request.data
        for field in ('username', 'email', 'password', 'full_name'):
            if not data.get(field):
                return Response({'error': f'{field} is required.'}, status=400)
        if User.objects.filter(username=data['username']).exists():
            return Response({'error': 'A user with that username already exists.'}, status=400)
        if User.objects.filter(email=data['email']).exists():
            return Response({'error': 'A user with that email already exists.'}, status=400)

        name_parts = data['full_name'].split(' ', 1)
        role = data.get('role', 'regular_user')
        try:
            user = User.objects.create_user(
                username=data['username'], email=data['email'], password=data['password'],
                first_name=name_parts[0], last_name=name_parts[1] if len(name_parts) > 1 else '',
            )
            user.is_active = True
            user.save(update_fields=['is_active'])

            CompanyUser.objects.create(company=company, user=user, role=role)

            module_names = ALL_MODULE_NAMES if role == 'company_admin' else (data.get('modules') or [])
            rbac_role = 'module_admin' if role == 'company_admin' else role
            for module in Module.objects.filter(name__in=module_names):
                UserModuleAccess.objects.create(user=user, module=module, role=rbac_role, granted_by=request.user)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

        return Response({'message': 'User added', 'user_id': user.id}, status=201)


class SwitchCompanyView(APIView):
    """Platform admin switches to view a specific company's data. There's no
    server-side session to update (see apps.companies.utils docstring) — this
    just validates the target exists/is active; the frontend is the one that
    remembers the choice and sends it back as X-Active-Company-Id on every
    subsequent request."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        _, is_platform_admin = resolve_company(request)
        if not is_platform_admin:
            return Response({'error': 'Not authorized'}, status=403)
        company_id = request.data.get('company_id')
        if not company_id:
            return Response({'message': 'Switched to all companies view'})
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Company not found'}, status=404)
        return Response({
            'message': f'Switched to {company.name}',
            'company': {'id': company.id, 'name': company.name},
        })


class MyCompanyView(APIView):
    """Get current user's company info."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company, is_platform_admin = resolve_company(request)
        if is_platform_admin:
            companies = Company.objects.filter(status='active')
            return Response({
                'is_platform_admin': True,
                'active_company': CompanySerializer(company).data if company else None,
                'all_companies': CompanySerializer(companies, many=True).data,
            })

        if not company:
            return Response({'error': 'No company assigned'}, status=400)

        return Response({
            'is_platform_admin': False,
            'company': CompanySerializer(company).data,
            'role': get_user_company_role(request.user),
        })
