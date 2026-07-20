"""Multi-tenant company resolution and scoping.

Deliberately NOT a Django middleware reading request.session — this backend
authenticates every /api/v1/ call via stateless JWT bearer tokens (see
apps.authentication), and the frontend's erpFetch() sends only an
Authorization header, no cookies, cross-origin (xerxez.com -> Railway). By
the time Django's own middleware chain runs, request.user is still
AnonymousUser; DRF only populates the real user once a view's
authentication_classes run during dispatch. So company resolution happens
here, called explicitly from views/mixins *after* DRF has authenticated the
request — the same place apps.rbac.utils already resolves role.

A platform admin's "active company" (the Company Switcher) has no session to
live in either, so it's sent by the frontend on every request as the
X-Active-Company-Id header (or ?company_id= for simple GETs), mirroring how
this app already keeps auth/role state client-side in localStorage rather
than server sessions.
"""
from .models import Company, CompanyUser


def resolve_company(request):
    """Returns (company, is_platform_admin) for the current request.

    - Unauthenticated -> (None, False)
    - Superuser (XERXEZ platform admin) -> is_platform_admin=True; company is
      whatever they've switched to via X-Active-Company-Id / ?company_id=, or
      None if they're in "All Companies" view.
    - Everyone else -> is_platform_admin=False; company is their one active
      CompanyUser membership, or None if unassigned.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return None, False

    if user.is_superuser:
        raw_id = request.headers.get('X-Active-Company-Id') or request.GET.get('company_id')
        if raw_id:
            try:
                return Company.objects.get(pk=int(raw_id)), True
            except (Company.DoesNotExist, ValueError, TypeError):
                pass
        return None, True

    return get_user_company(user), False


def get_company_queryset(queryset, company, is_platform_admin, company_field='company'):
    """Filter queryset by company. Platform admin with no company selected sees
    everything; platform admin who switched, or a regular company user, sees
    only that company's rows; anyone else sees nothing."""
    if is_platform_admin and not company:
        return queryset
    if company:
        try:
            return queryset.filter(**{company_field: company})
        except Exception:
            return queryset.none()
    return queryset.none()


def get_user_company(user):
    """Get the company a user belongs to."""
    try:
        return CompanyUser.objects.select_related('company').get(user=user, is_active=True).company
    except CompanyUser.DoesNotExist:
        return None


def get_user_company_role(user):
    """Get user's role in their company."""
    try:
        return CompanyUser.objects.get(user=user, is_active=True).role
    except CompanyUser.DoesNotExist:
        return None
