from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from news.domain import resolve_thread_type


class FrontendDomainMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.frontend_thread_type = resolve_thread_type(request)  # type: ignore[attr-defined]
        return self.get_response(request)
