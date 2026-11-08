"""Dziennik zdarzeń append-only, pseudonimowy: do analityki i widoków "Spór", "Zgoda", "Najgoręcej".

Żadnego klucza do użytkownika: `actor` to pseudonim z `Spina3Profile`; usunięcie profilu usuwa mapowanie.
Retencja: `ScoringConfig.event_retention_days` (propozycja 12 miesięcy, potem agregaty; do prawnika).
"""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from .config import config
from .models import PinEvent, Spina3Profile


def pseudonym(user) -> str:
    if user is None or not getattr(user, 'is_authenticated', False):
        return ''
    return Spina3Profile.for_user(user).pseudonym


def log(kind: str, box, *, pin=None, actor: str = '', before=None, after=None, meta: dict | None = None, now=None) -> PinEvent:
    return PinEvent.objects.create(kind=kind, box=box, pin_id=getattr(pin, 'pk', None), actor=actor or '',
                                   stance_before=before, stance_after=after, meta=meta or {}, created_at=now or timezone.now())


def count_recent(actor: str, kinds: tuple, hours: float = 24.0, now=None) -> int:
    now = now or timezone.now()
    return PinEvent.objects.filter(actor=actor, kind__in=kinds, created_at__gte=now - timedelta(hours=hours)).count()


def purge(now=None) -> int:
    """Usuwa zdarzenia starsze niż retencja (agregaty zostają w BoxSpinka)."""
    now = now or timezone.now()
    cutoff = now - timedelta(days=config().event_retention_days)
    deleted, _ = PinEvent.objects.filter(created_at__lt=cutoff).delete()
    return deleted
