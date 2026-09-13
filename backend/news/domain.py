from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest


def resolve_thread_type(request: HttpRequest) -> str | None:
    """Map X-Frontend-Domain / Host to Thread.thread_type."""
    domain = (
        request.headers.get("X-Frontend-Domain")
        or request.META.get("HTTP_X_FRONTEND_DOMAIN")
        or request.get_host()
    )
    domain = domain.split(",")[0].strip().lower()
    mapping: dict[str, str] = getattr(settings, "DOMAIN_THREAD_TYPE", {})
    if domain in mapping:
        return mapping[domain]
    # Host without port
    host = domain.split(":")[0]
    return mapping.get(host)
