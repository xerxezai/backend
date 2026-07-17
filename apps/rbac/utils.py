from .models import UserModuleAccess

# EPC modules are restricted to Super Admins only.
EPC_MODULES = ['document_management', 'project_management', 'asset_management', 'qhse']


def get_user_role(user, module_name=None):
    if not user or not user.is_authenticated:
        return 'no_access'
    if user.is_superuser:
        return 'super_admin'
    if module_name:
        try:
            access = UserModuleAccess.objects.get(user=user, module__name=module_name, is_active=True)
            return access.role
        except UserModuleAccess.DoesNotExist:
            return 'no_access'
    # Highest role across all modules the user has any access to.
    access = UserModuleAccess.objects.filter(user=user, is_active=True)
    if access.filter(role='super_admin').exists():
        return 'super_admin'
    if access.filter(role='module_admin').exists():
        return 'module_admin'
    if access.filter(role='regular_user').exists():
        return 'regular_user'
    if access.filter(role='read_only').exists():
        return 'read_only'
    return 'no_access'


def has_module_access(user, module_name):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if module_name in EPC_MODULES:
        return False  # EPC modules: super admin only (checked above)
    return UserModuleAccess.objects.filter(user=user, module__name=module_name, is_active=True).exists()


def filter_queryset_by_role(queryset, user, module_name, user_field='created_by'):
    role = get_user_role(user, module_name)
    if role == 'super_admin':
        # Sees everything
        return queryset
    if role in ('module_admin', 'regular_user', 'read_only'):
        # Module Admin, Regular User and Read Only all see only their own data
        return queryset.filter(**{user_field: user})
    # No access
    return queryset.none()
