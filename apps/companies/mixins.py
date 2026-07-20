"""Tenant-isolation-only mixin — no RBAC role-based owner narrowing on top.

Use this (instead of apps.rbac.mixins.RBACScopedMixin) for viewsets in apps
that were never part of the created_by/per-user RBAC rollout (HR ops records,
Documents, Project/Asset Management, QHSE): company scoping still applies as
a hard tenant boundary, but within a company every member with module access
sees all of that company's records for these models, since they generally
don't have a created_by field to narrow by.
"""
from .utils import resolve_company, get_company_queryset


class CompanyScopedMixin:
    company_field = 'company'
    company_stamp = True
    stamp_created_by = False  # flip on only for models that actually have created_by

    def _company_context(self):
        if not hasattr(self, '_company_ctx'):
            self._company_ctx = resolve_company(self.request)
        return self._company_ctx

    def company_scope(self, queryset):
        if not self.company_field:
            return queryset
        company, is_platform_admin = self._company_context()
        return get_company_queryset(queryset, company, is_platform_admin, self.company_field)

    def get_queryset(self):
        return self.company_scope(super().get_queryset())

    def perform_create(self, serializer):
        extra = {}
        if self.company_field and self.company_stamp:
            company, _ = self._company_context()
            extra[self.company_field] = company
        if self.stamp_created_by:
            extra['created_by'] = self.request.user
        serializer.save(**extra)
