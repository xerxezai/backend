from rest_framework.permissions import BasePermission, SAFE_METHODS

from .utils import has_module_access, get_user_role


class HasModuleAccess(BasePermission):
    module_name = None

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        module = getattr(view, 'module_name', self.module_name)
        if not module:
            return True
        return has_module_access(request.user, module)


class ReadOnlyOrHigher(BasePermission):
    module_name = None

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        role = get_user_role(request.user, self.module_name)
        if role == 'no_access':
            return False
        if role == 'read_only':
            return request.method in SAFE_METHODS
        return True
