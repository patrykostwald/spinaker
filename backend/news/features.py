"""Request-local feature overrides; workers keep their explicit settings checks."""
from contextvars import ContextVar
from django.conf import settings

preview_active = ContextVar('sc_preview_active', default=False)


def accounts_enabled():
    return bool(settings.ACCOUNTS_ENABLED or preview_active.get())


def threads_enabled():
    return bool(settings.THREADS_ENABLED or preview_active.get())


def push_enabled():
    return bool(settings.PUSH_ENABLED or preview_active.get())
