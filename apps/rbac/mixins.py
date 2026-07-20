"""Drop-in RBAC data-isolation mixin for ERP viewsets.

Rule enforced everywhere: super_admin sees ALL data; every other user sees ONLY
records they own (created_by = them, or an owner path through a parent FK for
child rows). Read-only users additionally cannot create/update/delete.

Usage:
    class ShipmentViewSet(RBACScopedMixin, viewsets.ModelViewSet):
        rbac_module = 'logistics'

    class QuotationItemViewSet(RBACScopedMixin, viewsets.ModelViewSet):
        rbac_module = 'sales'
        rbac_user_field = 'quotation__created_by'   # owned via parent
        rbac_stamp_created_by = False               # model has no created_by itself

A viewset that defines its own get_queryset() must call
`self.rbac_scope(qs)` at the end instead of relying on the mixin's version.
"""
from rest_framework.exceptions import PermissionDenied

from .utils import filter_queryset_by_role, get_user_role


class RBACScopedMixin:
    rbac_module = None
    rbac_user_field = 'created_by'
    rbac_stamp_created_by = True

    def rbac_scope(self, queryset):
        return filter_queryset_by_role(
            queryset, self.request.user, self.rbac_module, user_field=self.rbac_user_field,
        )

    def get_queryset(self):
        return self.rbac_scope(super().get_queryset())

    def _rbac_block_read_only(self):
        user = self.request.user
        if user.is_authenticated and not user.is_superuser \
                and get_user_role(user, self.rbac_module) == 'read_only':
            raise PermissionDenied('Read only access. You cannot create, edit or delete records.')

    def perform_create(self, serializer):
        self._rbac_block_read_only()
        if self.rbac_stamp_created_by:
            serializer.save(created_by=self.request.user)
        else:
            serializer.save()

    def perform_update(self, serializer):
        self._rbac_block_read_only()
        serializer.save()

    def perform_destroy(self, instance):
        self._rbac_block_read_only()
        super().perform_destroy(instance)
