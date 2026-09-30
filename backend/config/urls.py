from __future__ import annotations

from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from news import preview

urlpatterns = [
    # Avoid an APPEND_SLASH redirect echoing the secret query in Location.
    path("api/preview", preview.enter),
    path("api/preview/", preview.enter),
    path("api/preview/off/", preview.leave),
    path("api/preview/status/", preview.status),
    path("zasady-zrodel/", TemplateView.as_view(template_name="source-principles.html"), name="source-principles"),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    path("api/", include("news.urls")),
]
