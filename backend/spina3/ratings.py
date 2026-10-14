"""Oceny przypięcia autora (v2): zgadzam się (+1) / nie zgadzam się (-1), jedna na użytkownika i przypięcie,
zmiana (z odstępem) i wycofanie dozwolone. Z ocen powstaje S i ranking (spinka.recompute).

Zasady: ocenia się tylko opublikowane przypięcie z dostępnym dowodem (`Pin.ratable`); własnego przypięcia nie ocenia się;
Dr. Spin i konta T0 nie oceniają; zespół ocenia z wagą 0. Limity: dobowy (T1 30, T2 200), seria 10/min, odstęp 1 h na zmianę.
Kody: 400 dane, 403 uprawnienia, flaga, zgoda (consent) lub wiek (age), 404 brak przypięcia, 409 dowód niedostępny lub box zamrożony,
423 cisza (także cisza konta kandydata lub komitetu), 429 limit.
"""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from . import events
from .config import STANCES, config, election_silence, flags
from .legal import check_publish_consent, check_silence
from .models import Pin, Rating, Spina3Profile
from .pins import PinError
from .spinka import recompute
from .trust import trust_for


def parse_stance(value) -> int:
    if isinstance(value, str):
        value = value.strip()
        if value in STANCES:
            return STANCES[value]
        value = {'1': 1, '+1': 1, '-1': -1}.get(value, value)
    if value in (-1, 1) and not isinstance(value, bool):
        return int(value)
    raise PinError(400, 'Ocena: zgadzam się (agree, +1) albo nie zgadzam się (disagree, -1).', 'stance')


def _check_flags(now):
    fl = flags()
    if not fl.enabled or not fl.ratings_enabled:
        raise PinError(403, 'Oceny są wyłączone.', 'ratings_disabled')
    if election_silence(now)['ratings_paused']:
        raise PinError(423, 'Cisza wyborcza: oceny przyjmujemy po jej zakończeniu.', 'election_silence')


def _check_pin(pin: Pin, user):
    if pin.status != 'published' or pin.box.status != 'published':
        raise PinError(404, 'Nie ma takiego przypięcia.', 'pin')
    if pin.box.source_status != 'active':
        raise PinError(409, 'Materiał wycofany u źródła: ocena zamrożona.', 'frozen')
    if pin.target_status == 'pending':
        raise PinError(409, 'Dowód przypięcia czeka na weryfikację; ocenisz po decyzji zespołu.', 'target_pending')
    if pin.target_status != 'ok':
        raise PinError(409, 'Dowód przypięcia jest niedostępny; autor ma 7 dni na wymianę.', 'target_unavailable')
    if pin.user_id is not None and pin.user_id == getattr(user, 'pk', None):
        raise PinError(403, 'Własnego przypięcia nie da się ocenić.', 'own')


def _check_account(user, cfg, now):
    trust = trust_for(user, cfg, now)
    if trust.is_system or not trust.can_publish:
        raise PinError(403, 'To konto nie może oceniać: ' + (trust.reason or 'potwierdź e-mail.'), 'tier')
    profile = Spina3Profile.for_user(user)
    if profile.consent_art9_at is None and not trust.is_team:
        raise PinError(403, 'Przed pierwszą oceną potrzebna jest zgoda na publikację stanowisk przy nicku.', 'consent')
    check_publish_consent(profile, trust)
    return trust, profile


@transaction.atomic
def set_rating(user, pin: Pin, stance, now=None) -> tuple[Rating, dict]:
    """Tworzy ocenę albo zmienia istniejącą (także po wycofaniu). Zwraca (rating, {'spinka': ..., 'changed': bool})."""
    now = now or timezone.now()
    cfg = config()
    _check_flags(now)
    _check_pin(pin, user)
    check_silence(pin.box, now=now)
    trust, profile = _check_account(user, cfg, now)
    actor = profile.pseudonym
    value = parse_stance(stance)
    existing = Rating.objects.select_for_update().filter(user=user, pin=pin).first()
    if existing is not None and existing.status == 'active':
        if existing.stance == value:
            existing.account_weight, existing.is_team = trust.weight, trust.is_team
            existing.save(update_fields=['account_weight', 'is_team', 'updated_at'])
            return existing, {'spinka': recompute(pin.box, now, cfg), 'changed': False}
        last = existing.stance_changed_at or existing.created_at
        if now < last + timedelta(hours=cfg.rating_change_cooldown_hours):
            raise PinError(429, 'Ocenę można zmienić po godzinie od poprzedniej.', 'rating_cooldown')
        events.log('rating_changed', pin.box, pin=pin, actor=actor, before=existing.stance, after=value, now=now)
        existing.stance, existing.stance_changed_at = value, now
        existing.account_weight, existing.is_team = trust.weight, trust.is_team
        existing.save()
        return existing, {'spinka': recompute(pin.box, now, cfg), 'changed': True}
    if existing is not None and existing.stance != value:
        # wycofanie i ponowna ocena przeciwna nie omija odstępu na zmianę zdania
        last = existing.stance_changed_at or existing.created_at
        if now < last + timedelta(hours=cfg.rating_change_cooldown_hours):
            raise PinError(429, 'Ocenę można zmienić po godzinie od poprzedniej.', 'rating_cooldown')
    rated = events.count_recent(actor, ('rated',), 24, now)
    if rated >= trust.daily_ratings:
        raise PinError(429, f'Limit {trust.daily_ratings} ocen na dobę dla tego konta.', 'daily_limit')
    burst = events.count_recent(actor, ('rated',), cfg.burst_window_seconds / 3600, now)
    if burst >= cfg.burst_max_ratings:
        raise PinError(429, 'Za szybko: odczekaj chwilę przed kolejną oceną.', 'burst')
    rating = existing or Rating(user=user, pin=pin, box=pin.box)
    rating.stance, rating.status, rating.created_at = value, 'active', now
    rating.stance_changed_at, rating.withdrawn_at, rating.anonymized = None, None, False
    rating.account_weight, rating.is_team = trust.weight, trust.is_team
    rating.save()
    events.log('rated', pin.box, pin=pin, actor=actor, after=value, meta={'tier': trust.tier, 'again': existing is not None}, now=now)
    return rating, {'spinka': recompute(pin.box, now, cfg), 'changed': True}


@transaction.atomic
def withdraw_rating(user, pin: Pin, now=None) -> dict:
    now = now or timezone.now()
    cfg = config()
    _check_flags(now)
    rating = Rating.objects.select_for_update().filter(user=user, pin=pin, status='active').first()
    if rating is None:
        raise PinError(404, 'Nie masz oceny przy tym przypięciu.', 'rating')
    rating.status, rating.withdrawn_at = 'withdrawn', now
    rating.save(update_fields=['status', 'withdrawn_at', 'updated_at'])
    events.log('unrated', pin.box, pin=pin, actor=Spina3Profile.for_user(user).pseudonym, before=rating.stance, now=now)
    return {'spinka': recompute(pin.box, now, cfg)}


def my_rating(user, pin: Pin) -> Rating | None:
    if user is None or not getattr(user, 'is_authenticated', False):
        return None
    return Rating.objects.filter(user=user, pin=pin, status='active').first()
