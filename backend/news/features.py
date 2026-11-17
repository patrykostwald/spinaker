"""Podgląd kont i push; spinki mają jedną globalną flagę backendu."""
from contextvars import ContextVar
from django.conf import settings

preview_active = ContextVar('sc_preview_active', default=False)


def accounts_enabled():
    return bool(settings.ACCOUNTS_ENABLED or preview_active.get())


def threads_enabled():
    return bool(settings.THREADS_ENABLED)


def push_enabled():
    return bool(settings.PUSH_ENABLED or preview_active.get())


class ThreadsEnabledMixin:
    """Spinki wyłączone globalnie zwracają 404 również przed autoryzacją."""
    def initial(self, request, *args, **kwargs):
        if not threads_enabled():
            from django.http import Http404
            raise Http404
        return super().initial(request, *args, **kwargs)


def threads_disabled_result():
    import logging
    logging.getLogger(__name__).info('Spinki wyłączone (THREADS_ENABLED): pomijam zadanie.')
    return {'status': 'disabled'}
