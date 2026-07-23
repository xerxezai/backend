from django.contrib.auth import get_user_model
from django.utils.text import slugify
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.rbac.models import Module, UserModuleAccess
from apps.core.email import send_welcome_email
from .models import Company, CompanyUser
from .serializers import CompanySerializer, CompanyUserSerializer
from .utils import resolve_company, get_user_company, get_user_company_role

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
            company = serializer.save()
            from apps.hr.models import create_default_leave_policies
            create_default_leave_policies(company)
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

        current_users = CompanyUser.objects.filter(company=company, is_active=True).count()
        if current_users >= company.max_users:
            return Response({
                'error': f'User limit reached. This company can have a maximum of {company.max_users} users. '
                         f'Please contact XERXEZ to increase the limit.',
            }, status=400)

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

            # role is passed straight through to UserModuleAccess (including 'company_admin'
            # verbatim) — apps.rbac.utils.get_user_role() resolves it correctly since that
            # role became a real UserModuleAccess choice; no more downgrading it to
            # 'module_admin' the way this used to work around the old, incomplete role list.
            module_names = ALL_MODULE_NAMES if role == 'company_admin' else (data.get('modules') or [])
            for module in Module.objects.filter(name__in=module_names):
                UserModuleAccess.objects.create(user=user, module=module, role=role, granted_by=request.user)
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


def _resolve_my_company(request):
    """(company, error_response) — Company Admin manages their own company; a Super
    Admin manages whichever company they've switched to via the Company Switcher."""
    if request.user.is_superuser:
        company, _ = resolve_company(request)
        if not company:
            return None, Response({'error': 'Switch to a company first.'}, status=400)
        return company, None
    if get_user_company_role(request.user) != 'company_admin':
        return None, Response({'error': 'Company Admin access required.'}, status=403)
    company = get_user_company(request.user)
    if not company:
        return None, Response({'error': 'No company assigned.'}, status=400)
    return company, None


class MyCompanyUsersView(APIView):
    """Company Admin self-service — list/add users within their own company only.
    Mirrors CompanyUsersView but is scoped to the caller's own company (resolved from
    the JWT, never a company_id in the URL) and can never create a Super Admin or
    another Company Admin."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company, err = _resolve_my_company(request)
        if err:
            return err
        users = CompanyUser.objects.select_related('user').filter(company=company)
        return Response(CompanyUserSerializer(users, many=True).data)

    def post(self, request):
        company, err = _resolve_my_company(request)
        if err:
            return err

        role = request.data.get('role', 'regular_user')
        if role in ('super_admin', 'company_admin'):
            return Response({'error': 'You cannot create a Super Admin or Company Admin account.'}, status=403)

        current_users = CompanyUser.objects.filter(company=company, is_active=True).count()
        if current_users >= company.max_users:
            return Response({
                'error': f'User limit reached. This company can have a maximum of {company.max_users} users. '
                         f'Contact XERXEZ to increase your limit.',
            }, status=400)

        data = request.data
        for field in ('username', 'email', 'password', 'full_name'):
            if not data.get(field):
                return Response({'error': f'{field} is required.'}, status=400)
        if User.objects.filter(username=data['username']).exists():
            return Response({'error': 'A user with that username already exists.'}, status=400)
        if User.objects.filter(email=data['email']).exists():
            return Response({'error': 'A user with that email already exists.'}, status=400)
        if not data.get('modules'):
            return Response({'error': 'Assign at least one module for this role.'}, status=400)

        name_parts = data['full_name'].split(' ', 1)
        try:
            user = User.objects.create_user(
                username=data['username'], email=data['email'], password=data['password'],
                first_name=name_parts[0], last_name=name_parts[1] if len(name_parts) > 1 else '',
            )
            user.is_active = True
            user.save(update_fields=['is_active'])
            CompanyUser.objects.create(company=company, user=user, role=role)
            for module in Module.objects.filter(name__in=data.get('modules') or []):
                UserModuleAccess.objects.create(user=user, module=module, role=role, granted_by=request.user)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

        send_welcome_email(
            full_name=data['full_name'], email=user.email, username=user.username,
            password=data['password'], company_name=company.name, role=role,
        )

        return Response({'message': 'User added', 'user_id': user.id}, status=201)


class MyCompanyUserDetailView(APIView):
    """Company Admin self-service — edit or deactivate one user in their own company.
    Never touches Super Admin or Company Admin accounts."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_membership(self, company, user_id):
        try:
            return CompanyUser.objects.select_related('user').get(company=company, user_id=user_id), None
        except CompanyUser.DoesNotExist:
            return None, Response({'error': 'User not found in your company.'}, status=404)

    def put(self, request, user_id):
        company, err = _resolve_my_company(request)
        if err:
            return err
        membership, err = self._get_membership(company, user_id)
        if err:
            return err
        if membership.user.is_superuser or membership.role in ('super_admin', 'company_admin'):
            return Response({'error': 'You cannot edit a Super Admin or Company Admin account.'}, status=403)

        new_role = request.data.get('role')
        if new_role in ('super_admin', 'company_admin'):
            return Response({'error': 'You cannot promote a user to Super Admin or Company Admin.'}, status=403)
        if new_role:
            membership.role = new_role
            membership.save(update_fields=['role'])

        modules = request.data.get('modules')
        if modules is not None:
            UserModuleAccess.objects.filter(user=membership.user).delete()
            for module in Module.objects.filter(name__in=modules):
                UserModuleAccess.objects.create(
                    user=membership.user, module=module, role=new_role or membership.role, granted_by=request.user,
                )

        return Response(CompanyUserSerializer(membership).data)

    def delete(self, request, user_id):
        company, err = _resolve_my_company(request)
        if err:
            return err
        membership, err = self._get_membership(company, user_id)
        if err:
            return err
        if membership.user.is_superuser or membership.role in ('super_admin', 'company_admin'):
            return Response(
                {'error': 'You cannot deactivate a Super Admin or Company Admin. Contact XERXEZ to remove admin access.'},
                status=403,
            )
        membership.is_active = False
        membership.save(update_fields=['is_active'])
        membership.user.is_active = False
        membership.user.save(update_fields=['is_active'])
        return Response({'message': 'User deactivated'})


class MyCompanyStatsView(APIView):
    """Company Admin self-service — user-limit usage for their own company."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company, err = _resolve_my_company(request)
        if err:
            return err
        active = CompanyUser.objects.filter(company=company, is_active=True)
        current = active.count()
        return Response({
            'company_name': company.name,
            'max_users': company.max_users,
            'current_users': current,
            'remaining_slots': max(company.max_users - current, 0),
            'users_by_role': {choice[0]: active.filter(role=choice[0]).count() for choice in CompanyUser.ROLE_CHOICES},
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
