from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Module, UserModuleAccess, AccessRequest
from .serializers import (
    ModuleSerializer, UserListSerializer, CreateUserSerializer,
    AccessRequestSerializer,
)
from .utils import get_user_role

User = get_user_model()


class IsSuperAdmin(IsAuthenticated):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and (request.user.is_superuser or get_user_role(request.user) == 'super_admin')
        )


class ModuleListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        modules = Module.objects.filter(is_active=True)
        return Response(ModuleSerializer(modules, many=True).data)


class MyAccessView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        is_super = user.is_superuser or get_user_role(user) == 'super_admin'
        if is_super:
            modules = Module.objects.filter(is_active=True)
            module_data = [
                {'name': m.name, 'display_name': m.display_name, 'role': 'super_admin', 'icon': m.icon}
                for m in modules
            ]
        else:
            access = UserModuleAccess.objects.filter(user=user, is_active=True).select_related('module')
            module_data = [
                {'name': a.module.name, 'display_name': a.module.display_name, 'role': a.role, 'icon': a.module.icon}
                for a in access
            ]
        return Response({
            'user_id': user.id,
            'username': user.username,
            'full_name': user.get_full_name() or user.username,
            'is_super_admin': is_super,
            'role': get_user_role(user),
            'modules': module_data,
        })


class UserManagementView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        users = User.objects.all().prefetch_related('module_access__module')
        return Response(UserListSerializer(users, many=True).data)

    def post(self, request):
        serializer = CreateUserSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        name_parts = data['full_name'].split(' ', 1)
        user = User.objects.create_user(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            first_name=name_parts[0],
            last_name=name_parts[1] if len(name_parts) > 1 else '',
        )
        user.is_active = True
        user.save()
        role = data['role']
        if role == 'super_admin':
            user.is_superuser = True
            user.is_staff = True
            user.save(update_fields=['is_superuser', 'is_staff'])
            modules = Module.objects.filter(is_active=True)
        else:
            modules = Module.objects.filter(name__in=data.get('modules', []))
        for module in modules:
            UserModuleAccess.objects.create(user=user, module=module, role=role, granted_by=request.user)
        return Response({'message': 'User created', 'user_id': user.id}, status=status.HTTP_201_CREATED)


class UserDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsSuperAdmin]

    def put(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)
        role = request.data.get('role')
        modules = request.data.get('modules', [])
        if role:
            # Keep the Django is_superuser/is_staff flags in sync with the RBAC role —
            # UserManagementView.post() sets them on create, but nothing previously kept
            # them in sync on edit. Since UserListSerializer's Role/Modules columns check
            # is_superuser before module_access, a Super Admin demoted here would keep
            # showing "Super Admin" / "All modules" forever even though their
            # UserModuleAccess rows below were correctly rewritten.
            is_super = role == 'super_admin'
            if user.is_superuser != is_super or user.is_staff != is_super:
                user.is_superuser = is_super
                user.is_staff = is_super
                user.save(update_fields=['is_superuser', 'is_staff'])
        if modules:
            UserModuleAccess.objects.filter(user=user).delete()
            for module_name in modules:
                try:
                    module = Module.objects.get(name=module_name)
                    UserModuleAccess.objects.create(
                        user=user, module=module, role=role or 'regular_user', granted_by=request.user,
                    )
                except Module.DoesNotExist:
                    pass
        elif role:
            UserModuleAccess.objects.filter(user=user).update(role=role)
        return Response({'message': 'User updated'})

    def delete(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)
        user.is_active = False
        user.save(update_fields=['is_active'])
        return Response({'message': 'User deactivated'})


class GrantAccessView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsSuperAdmin]

    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            module = Module.objects.get(name=request.data['module_name'])
        except (User.DoesNotExist, Module.DoesNotExist, KeyError) as e:
            return Response({'error': str(e)}, status=400)
        access, created = UserModuleAccess.objects.get_or_create(
            user=user, module=module,
            defaults={'role': request.data.get('role', 'regular_user'), 'granted_by': request.user, 'is_active': True},
        )
        if not created:
            access.role = request.data.get('role', access.role)
            access.is_active = True
            access.save(update_fields=['role', 'is_active'])
        return Response({'message': 'Access granted'})

    def delete(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            module = Module.objects.get(name=request.data['module_name'])
        except (User.DoesNotExist, Module.DoesNotExist, KeyError) as e:
            return Response({'error': str(e)}, status=400)
        UserModuleAccess.objects.filter(user=user, module=module).update(is_active=False)
        return Response({'message': 'Access revoked'})


class AccessRequestView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_superuser or get_user_role(request.user) == 'super_admin':
            requests_qs = AccessRequest.objects.all()
        else:
            requests_qs = AccessRequest.objects.filter(user=request.user)
        serializer = AccessRequestSerializer(requests_qs.select_related('user', 'module', 'reviewed_by').order_by('-created_at'), many=True)
        return Response(serializer.data)

    def post(self, request):
        try:
            module = Module.objects.get(name=request.data['module_name'])
        except (Module.DoesNotExist, KeyError) as e:
            return Response({'error': str(e)}, status=400)
        AccessRequest.objects.create(user=request.user, module=module, reason=request.data.get('reason', ''))
        return Response({'message': 'Access request submitted'}, status=201)


class AccessRequestActionView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsSuperAdmin]

    def put(self, request, request_id, action):
        if action not in ('approve', 'reject'):
            return Response({'error': 'action must be "approve" or "reject".'}, status=400)
        try:
            access_request = AccessRequest.objects.get(id=request_id)
        except AccessRequest.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        if action == 'approve':
            access_request.status = 'approved'
            access, _ = UserModuleAccess.objects.get_or_create(
                user=access_request.user, module=access_request.module,
                defaults={'role': 'regular_user', 'granted_by': request.user, 'is_active': True},
            )
            access.is_active = True
            access.save(update_fields=['is_active'])
        else:
            access_request.status = 'rejected'
        access_request.reviewed_by = request.user
        access_request.reviewed_at = timezone.now()
        access_request.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
        return Response({'message': f'Request {action}d'})
