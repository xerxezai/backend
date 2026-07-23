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
        if request.user.is_superuser:
            return True
        # Company Admin's authority spans every module — checked globally (highest role
        # across ANY module) rather than scoped to this view's module specifically. Their
        # UserModuleAccess grant for this exact module can be missing or incomplete (an
        # Edit Access edit that didn't re-include it, or any account whose per-module grants
        # are simply incomplete) without that meaning anything about their actual role — same
        # reasoning apps.hr.views._is_hr_privileged and RBACScopedMixin.rbac_scope() already
        # document for the identical check.
        if get_user_role(request.user) == 'company_admin':
            return True
        # Bug fix: this used to read self.module_name, which is never set (it's the
        # permission class's own default of None, not the view's) — every ReadOnlyOrHigher
        # check was silently falling back to the user's *global* highest role across all
        # modules instead of their role in view.module_name specifically. Matches the
        # getattr(view, 'module_name', ...) pattern HasModuleAccess (above) already uses.
        module = getattr(view, 'module_name', self.module_name)
        role = get_user_role(request.user, module)
        if role == 'no_access':
            return False
        if role == 'read_only':
            return request.method in SAFE_METHODS
        return True
