"""Poziomy zaufania kont (PETLA 2.3; lekki proof-of-personhood bez telefonu i bez dowodu).

T0: e-mail niepotwierdzony i brak konta X: oglądanie i szkic, bez publikacji.
T1: potwierdzony, < 14 dni lub < 5 aktywności: waga 0,5; limity T1 (3 boxy, 30 ocen, 10 komentarzy na dobę); bez URL.
T2: >= 14 dni, >= 5 opublikowanych aktywności (przypięcia, oceny, komentarze widoczne) w >= 3 różnych osobach lub podmiotach,
    0 ukryć: waga 1; limity T2; URL.
T3: ręcznie (zespół) albo konto połączone z X: jak T2 plus box z linku widoczny od razu; bez przywilejów w S.
Reputacja nigdy nie jest wyświetlana. Różnorodność liczymy po BOXACH (osoby, podmioty), nie po stanowiskach.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from .config import ScoringConfig, config
from .models import Comment, Pin, Rating, Spina3Profile


@dataclass(frozen=True)
class Trust:
    tier: str                 # 'T0' | 'T1' | 'T2' | 'T3' | 'team' | 'system'
    weight: float
    daily_limit: int          # boxy z przypięciem na dobę
    can_publish: bool
    can_pin_url: bool
    is_team: bool = False
    is_system: bool = False
    trusted: bool = False     # konto >= 7 dni i waga pełna: ustawia last_rating_at, liczy się do "Najgoręcej"
    reason: str = ''
    daily_ratings: int = 0
    daily_comments: int = 0


def email_verified(user) -> bool:
    identity = getattr(user, 'account_identity', None)
    return bool(identity and identity.email_verified)


def has_x(user) -> bool:
    return hasattr(user, 'x_connection')


def _subject_of(box) -> set:
    people = box.persons or []
    if people:
        return {('p', person.get('id') or person.get('name')) for person in people}
    if box.author_handle:
        return {('h', box.author_handle)}
    return {('d', box.source_domain or box.pk)}


def activity(user) -> tuple[int, int]:
    """(liczba opublikowanych aktywności, liczba różnych osób lub podmiotów) z przypięć, ocen i komentarzy konta."""
    subjects: set = set()
    count = 0
    for pin in Pin.objects.filter(user=user, status='published').exclude(kind='diagnosis').select_related('box'):
        count += 1
        subjects |= _subject_of(pin.box)
    for rating in Rating.objects.filter(user=user, status='active').select_related('box'):
        count += 1
        subjects |= _subject_of(rating.box)
    for comment in Comment.objects.filter(user=user, status='visible').select_related('box'):
        count += 1
        subjects |= _subject_of(comment.box)
    return count, len(subjects)


def distinct_subjects(user) -> int:
    return activity(user)[1]


def trust_for(user, cfg: ScoringConfig | None = None, now=None) -> Trust:
    cfg = cfg or config()
    now = now or timezone.now()
    if user is None or not getattr(user, 'is_authenticated', False):
        return Trust('T0', 0.0, 0, False, False, reason='anonim')
    profile = Spina3Profile.for_user(user)
    if profile.is_system:
        return Trust('system', 0.0, 0, False, False, is_system=True, reason='Dr. Spin nie głosuje')
    if profile.suspended_until and profile.suspended_until > now:
        return Trust('T0', 0.0, 0, False, False, reason='zawieszenie publikowania')
    if profile.is_team:
        return Trust('team', cfg.weight_team, cfg.daily_pins.get('team', 0) or 10 ** 6, True, True, is_team=True, trusted=True,
                     reason='zespół: kontekst, nie głos', daily_ratings=cfg.daily_ratings.get('team', 0),
                     daily_comments=cfg.daily_comments.get('team', 10 ** 6))
    if not email_verified(user) and not has_x(user):
        return Trust('T0', cfg.weight_tier['T0'], cfg.daily_pins['T0'], False, False, reason='e-mail niepotwierdzony')
    age = now - (user.date_joined or now)
    old_enough = age >= timedelta(days=cfg.young_account_days)
    week_old = age >= timedelta(days=7)
    zero_weight = bool(profile.weight_zero_until and profile.weight_zero_until > now)
    if profile.tier_manual == 'T3' or has_x(user):
        tier = 'T3'
    elif profile.tier_manual == 'T2' and old_enough and profile.hidden_count == 0:
        tier = 'T2'   # nadany przez zespół (np. biuro poselskie, redakcja) bez przywilejów T3
    elif old_enough and profile.hidden_count == 0:
        published, subjects = activity(user)
        tier = 'T2' if published >= cfg.young_account_min_activity and subjects >= cfg.tier2_min_distinct_subjects else 'T1'
    else:
        tier = 'T1'
    weight = 0.0 if zero_weight else cfg.weight_tier[tier]
    return Trust(tier, weight, cfg.daily_pins[tier], True, tier in ('T2', 'T3'),
                 trusted=week_old and weight >= 1.0, reason='waga 0 (sankcja)' if zero_weight else '',
                 daily_ratings=cfg.daily_ratings[tier], daily_comments=cfg.daily_comments[tier])
