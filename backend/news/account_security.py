"""Shared account feature and publication checks."""
from django.conf import settings
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import BasePermission


class AccountEnabled(BasePermission):
    def has_permission(self, request, view):
        if not settings.ACCOUNTS_ENABLED:
            raise NotFound()
        return True


def require_verified(user):
    if settings.ACCOUNTS_ENABLED:
        identity = getattr(user, 'account_identity', None)
        if not identity or not identity.email_verified:
            raise PermissionDenied('Potwierdź e-mail, zanim opublikujesz nitkę lub opinię.')
