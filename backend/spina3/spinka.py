"""Przeliczanie zmaterializowanej oceny boxa (BoxSpinka) z OCEN przypięcia autora: transakcyjnie po każdej zmianie.

Wagi: `Rating.account_weight` (zapisana przy ostatnim przeliczeniu konta) x 1/rozmiar klastra; zespół 0; oceny wycofane
nie liczą. Oceny liczą się tylko, gdy box ma opublikowane przypięcie z dostępnym dowodem (`Pin.ratable`); inaczej spinka
jest Otwarta z powodem `no_pin` albo `target_unavailable`. Box wycofany u źródła lub przez moderację ma S zamrożone.
"""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from . import scoring
from .config import OPEN, ScoringConfig, config
from .models import Box, BoxSpinka, Pin, Rating


def rating_input(rating: Rating, now, counts: bool = True) -> scoring.RatingInput:
    user = rating.user
    profile = getattr(user, 'spina3_profile', None) if user is not None else None
    cluster_size = profile.cluster_size if profile else 1
    weight = scoring.rating_weight(rating.account_weight, cluster_size, rating.is_team)
    joined = getattr(user, 'date_joined', None)
    week_old = bool(joined and joined <= now - timedelta(days=7)) or rating.anonymized
    return scoring.RatingInput(stance=rating.stance, weight=weight, created_at=rating.created_at,
                               trusted=week_old and weight >= 1.0 and not rating.is_team,
                               stance_changed_at=rating.stance_changed_at, counts=counts and rating.counts)


def daily_average(ratings: list[Rating], now, days: int = 7) -> float:
    since = now - timedelta(days=days)
    recent = [r for r in ratings if r.counts and r.created_at >= since]
    return len(recent) / days


def active_pin(box: Box) -> Pin | None:
    return Pin.objects.filter(box=box).exclude(status='removed').first()


@transaction.atomic
def recompute(box: Box, now=None, cfg: ScoringConfig | None = None) -> BoxSpinka:
    cfg = cfg or config()
    now = now or timezone.now()
    sp, _ = BoxSpinka.objects.select_for_update().get_or_create(box=box)
    frozen = box.source_status != 'active' or box.status == 'hidden'
    if frozen:
        if not sp.frozen:
            sp.frozen, sp.level_reason = True, 'frozen'
            sp.save(update_fields=['frozen', 'level_reason', 'updated_at'])
        return sp
    pin = active_pin(box)
    ratable = pin is not None and pin.ratable
    ratings = list(Rating.objects.filter(box=box).select_related('user__spina3_profile'))
    inputs = [rating_input(r, now, counts=True) for r in ratings]
    agg = scoring.aggregate(inputs, cfg, now)
    previous = scoring.LevelResult(sp.level, sp.level_raw or None, sp.level_reason, sp.level_pending)
    if ratable:
        result = scoring.level_transition(
            agg.s, agg.weighted_n, previous, cfg, raw_n=agg.n, now=now,
            first_rating_at=agg.first_rating_at or sp.first_rating_at, level_changed_at=sp.level_changed_at)
    else:
        reason = 'no_pin' if pin is None or pin.status != 'published' else 'target_unavailable'
        result = scoring.LevelResult(OPEN, scoring.band_with_hysteresis(agg.s, sp.level_raw or None, cfg), reason)
    if result.level != sp.level:
        sp.level_changed_at = now
    sp.n, sp.weighted_n, sp.weighted_sum, sp.score = agg.n, agg.weighted_n, agg.weighted_sum, agg.s
    sp.level, sp.level_raw, sp.level_reason, sp.level_pending = result.level, result.level_raw or '', result.reason, result.pending
    sp.first_rating_at, sp.last_rating_at = agg.first_rating_at or sp.first_rating_at, agg.last_rating_at
    sp.distribution = dict(agg.distribution)
    sp.views = scoring.views(agg, cfg, daily_average(ratings, now)) if ratable else {}
    sp.frozen = False
    sp.save()
    return sp


def recompute_many(box_ids, now=None) -> int:
    count = 0
    for box in Box.objects.filter(pk__in=list(box_ids)):
        recompute(box, now)
        count += 1
    return count


def refresh_account_weights(now=None) -> int:
    """Odświeża zapisane wagi kont we wszystkich ocenach (wiek konta, aktywność, sankcje) i przelicza boxy."""
    from .trust import trust_for
    now = now or timezone.now()
    touched: set[int] = set()
    users = {r.user_id for r in Rating.objects.filter(user__isnull=False).only('user_id')}
    from django.contrib.auth import get_user_model
    for user in get_user_model().objects.filter(pk__in=users):
        trust = trust_for(user, now=now)
        for rating in Rating.objects.filter(user=user):
            if abs(rating.account_weight - trust.weight) > 1e-9 or rating.is_team != trust.is_team:
                rating.account_weight, rating.is_team = trust.weight, trust.is_team
                rating.save(update_fields=['account_weight', 'is_team', 'updated_at'])
                touched.add(rating.box_id)
    return recompute_many(touched, now)


def refresh_clusters(now=None, days: int = 30) -> dict:
    """Wykrywa klastry kont zależnych na ocenach z ostatnich dni i zapisuje rozmiar klastra w profilach."""
    from .models import Spina3Profile
    cfg = config()
    now = now or timezone.now()
    since = now - timedelta(days=days)
    rows = Rating.objects.filter(created_at__gte=since, user__isnull=False, status='active') \
        .values_list('user_id', 'pin_id', 'stance', 'created_at')
    records = [scoring.RatingRecord(str(u), p, s, t) for u, p, s, t in rows]
    groups = scoring.cluster_groups(records, cfg)
    membership = {u: (f'c{min(int(m) for m in members)}', len(members)) for members in groups for u in members}
    touched: set[int] = set()
    user_ids = [int(u) for u in {r.user for r in records}]
    from django.contrib.auth import get_user_model
    for user_id in user_ids:
        user = get_user_model().objects.filter(pk=user_id).first()
        if user is None:
            continue
        profile = Spina3Profile.for_user(user)
        cluster_id, size = membership.get(str(user_id), ('', 1))
        if profile.cluster_size != size or profile.cluster_id != cluster_id:
            profile.cluster_size, profile.cluster_id = size, cluster_id
            profile.save(update_fields=['cluster_size', 'cluster_id'])
            touched.update(Rating.objects.filter(user_id=user_id).values_list('box_id', flat=True))
    recompute_many(touched, now)
    return {u: size for u, (_, size) in membership.items()}
