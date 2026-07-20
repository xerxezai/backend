"""Drop-in RBAC + multi-tenant data-isolation mixin for ERP viewsets.

Two layers compose here, always in this order:
  1. Tenant isolation (apps.companies): a hard boundary. Platform admins
     (XERXEZ superusers) see everything, or everything within whichever
     company they've switched to; every company user sees only their own
     company's rows, full stop.
  2. RBAC role scoping (apps.rbac): *within* that tenant boundary, super_admin
     and company_admin see all of it; module_admin/regular_user/read_only see
     only records they personally created.

Usage:
    class ShipmentViewSet(RBACScopedMixin, viewsets.ModelViewSet):
        rbac_module = 'logistics'

    class QuotationItemViewSet(RBACScopedMixin, viewsets.ModelViewSet):
        rbac_module = 'sales'
        rbac_user_field = 'quotation__created_by'   # owned via parent
        rbac_stamp_created_by = False                # model has no created_by itself

    class CustomerViewSet(RBACScopedMixin, viewsets.ModelViewSet):
        rbac_module = 'crm'
        company_field = 'tenant'   # Customer's own `company` field is a free-text
                                    # business field, not the tenant FK — see models.py

A viewset that defines its own get_queryset() must call
`self.rbac_scope(qs)` at the end instead of relying on the mixin's version.
"""
from rest_framework.exceptions import PermissionDenied

from .utils import filter_queryset_by_role, get_user_role


class RBACScopedMixin:
    rbac_module = None
    rbac_user_field = 'created_by'
    rbac_stamp_created_by = True
    company_field = 'company'   # set to None on models with no tenant FK (rare)
    company_stamp = True

    def _company_context(self):
        # Cached per-request-object since a single view dispatch may call this
        # more than once (get_queryset + perform_create).
        if not hasattr(self, '_rbac_company_ctx'):
            from apps.companies.utils import resolve_company
            self._rbac_company_ctx = resolve_company(self.request)
        return self._rbac_company_ctx

    def rbac_scope(self, queryset):
        company, is_platform_admin = self._company_context()

        if self.company_field:
            from apps.companies.utils import get_company_queryset
            queryset = get_company_queryset(queryset, company, is_platform_admin, self.company_field)

        # Platform admin sees everything within scope (all companies, or the one
        # they've switched to) — same "no further narrowing" treatment super_admin
        # already gets from filter_queryset_by_role, just extended across the
        # tenant dimension too.
        if is_platform_admin:
            return queryset

        # A Company Admin sees everything within their own company (they're the
        # super_admin of that one tenant), not just what they personally created.
        if company:
            from apps.companies.utils import get_user_company_role
            if get_user_company_role(self.request.user) == 'company_admin':
                return queryset

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
        extra = {}
        if self.rbac_stamp_created_by:
            extra['created_by'] = self.request.user
        if self.company_field and self.company_stamp:
            company, _ = self._company_context()
            extra[self.company_field] = company
        serializer.save(**extra)

    def perform_update(self, serializer):
        self._rbac_block_read_only()
        serializer.save()

    def perform_destroy(self, instance):
        self._rbac_block_read_only()
        super().perform_destroy(instance)
