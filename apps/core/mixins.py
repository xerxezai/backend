from django.db.models.deletion import ProtectedError
from rest_framework import status
from rest_framework.response import Response


class ProtectedDestroyMixin:
    """Turns Django's ProtectedError (raised when deleting a row still referenced by
    a PROTECT foreign key, e.g. a Customer with existing Invoices/SalesOrders) into a
    clean 409 response instead of an unhandled 500."""

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError as exc:
            blockers = sorted({str(obj) for obj in exc.protected_objects})
            return Response(
                {
                    'detail': "Can't delete — it's still referenced by other records.",
                    'blocked_by': blockers[:20],
                },
                status=status.HTTP_409_CONFLICT,
            )
