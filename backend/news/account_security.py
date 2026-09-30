"""Shared account feature and publication checks."""
from news.features import accounts_enabled
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import BasePermission


class AccountEnabled(BasePermission):
    def has_permission(self, request, view):
        if not accounts_enabled():
            raise NotFound()
        return True


def require_verified(user):
    if accounts_enabled():
        identity = getattr(user, 'account_identity', None)
        if not identity or not identity.email_verified:
            raise PermissionDenied('Potwierdź e-mail, zanim opublikujesz nitkę lub opinię.')
