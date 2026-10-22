"""Metryki jakości z agregatów serwera, bez śledzenia (PETLA sekcja 4, v2). "Liczymy oceny, nie ludzi."

Źródła: Rating, Pin, Comment, BoxSpinka, PinEvent (pseudonimowy), BoxDailyCounter (otwarcia boxa per doba, bez IP), kolejki moderacji.
Alarmy to wpis do raportu i decyzja człowieka, nie automat.
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from .config import LEVELS, config
from .models import Box, BoxDailyCounter, BoxSpinka, Comment, Pin, PinEvent, Rating, Report, Spina3Profile, UrlCheck


def count_view(box: Box, now=None) -> None:
    now = now or timezone.now()
    day = timezone.localdate(now)
    row, _ = BoxDailyCounter.objects.get_or_create(box=box, day=day)
    BoxDailyCounter.objects.filter(pk=row.pk).update(views=row.views + 1)


def compute(now=None, days: int = 7) -> dict:
    cfg = config()
    now = now or timezone.now()
    since = now - timedelta(days=days)
    period = now - timedelta(days=cfg.default_period_days)
    active = Rating.objects.filter(status='active')
    recent = active.filter(created_at__gte=since)
    pins_recent = Pin.objects.filter(status='published', created_at__gte=since).exclude(kind='diagnosis')
    comments_recent = Comment.objects.filter(created_at__gte=since).exclude(status='removed')
    boxes = Box.objects.filter(status='published', published_at__gte=period)
    rated = BoxSpinka.objects.filter(box__in=boxes, level__in=LEVELS).count()
    total_boxes = boxes.count()
    views = BoxDailyCounter.objects.filter(day__gte=timezone.localdate(since)).aggregate(total=Sum('views'))['total'] or 0
    ratings_week = recent.count()
    # 4.3: udział autorów jednej partii w top-20 (atrybut publiczny polityków)
    top = list(BoxSpinka.objects.filter(box__in=boxes, level__in=LEVELS).select_related('box').order_by('-level', '-last_rating_at')[:20])
    groups = Counter(sp.box.author_group for sp in top if sp.box.author_group)
    top_share = (groups.most_common(1)[0][1] / len(top)) if top and groups else 0.0
    # 4.4-4.6
    eligible = BoxSpinka.objects.filter(box__in=boxes, weighted_n__gte=cfg.views_min_n)
    dispute = sum(1 for sp in eligible if (sp.views or {}).get('dispute'))
    stances = Counter(recent.values_list('stance', flat=True))
    targets = Counter(pins_recent.exclude(pinned_box__isnull=True).values_list('pinned_box_id', flat=True))
    top10 = sum(c for _, c in targets.most_common(10))
    pins_week = pins_recent.count()
    # 4.7
    tier2 = recent.filter(account_weight__gte=1.0).count()
    clustered = recent.filter(user__spina3_profile__cluster_size__gt=1).count()
    young = recent.filter(user__date_joined__gte=now - timedelta(days=7)).count()
    url_total = UrlCheck.objects.filter(created_at__gte=since).count()
    url_rejected = UrlCheck.objects.filter(created_at__gte=since, status='rejected').count()
    # 4.8
    decided = Report.objects.filter(reviewed_at__isnull=False, created_at__gte=since)
    durations = sorted((r.reviewed_at - r.created_at).total_seconds() / 3600 for r in decided)
    median = durations[len(durations) // 2] if durations else None
    # 4.9: zmiany poziomu na box na 100 ocen przy n > 10
    big = BoxSpinka.objects.filter(n__gt=10)
    big_ids = list(big.values_list('box_id', flat=True))
    level_changes = sum(1 for sp in big if sp.level_changed_at and sp.level_changed_at >= since)
    ratings_big = PinEvent.objects.filter(box_id__in=big_ids, kind='rated', created_at__gte=since).count()
    stability = (level_changes / ratings_big * 100) if ratings_big else 0.0
    # 4.10: powrót oceniających
    week_now = set(recent.values_list('user_id', flat=True))
    week_prev = set(active.filter(created_at__gte=since - timedelta(days=days), created_at__lt=since).values_list('user_id', flat=True))
    returning = (len(week_now & week_prev) / len(week_prev)) if week_prev else None
    # 4.11: komentarze
    comments_total = comments_recent.count()
    comments_hidden = comments_recent.filter(status='hidden').count()
    comments_held = comments_recent.filter(status='held').count()
    out = {
        'period_days': days,
        'm4_1_ratings_per_100_views': round(ratings_week / views * 100, 2) if views else None,
        'm4_2_rated_share': round(rated / total_boxes, 3) if total_boxes else 0.0,
        'm4_3_top20_group_share': round(top_share, 3),
        'm4_4_dispute_index': round(dispute / eligible.count(), 3) if eligible.count() else None,
        'm4_5_stances': {'agree': stances.get(1, 0), 'disagree': stances.get(-1, 0)},
        'm4_6_top10_target_share': round(top10 / pins_week, 3) if pins_week else None,
        'm4_7_accounts': {'tier2_share': round(tier2 / ratings_week, 3) if ratings_week else None,
                          'cluster_share': round(clustered / ratings_week, 3) if ratings_week else None,
                          'young_share': round(young / ratings_week, 3) if ratings_week else None,
                          'url_rejected_share': round(url_rejected / url_total, 3) if url_total else None},
        'm4_8_moderation': {'reports_per_1000_ratings': round(Report.objects.filter(created_at__gte=since).count() / ratings_week * 1000, 2) if ratings_week else None,
                            'median_decision_hours': round(median, 1) if median is not None else None},
        'm4_9_level_changes_per_100_ratings_n_gt_10': round(stability, 2),
        'm4_10_returning_raters': round(returning, 3) if returning is not None else None,
        'm4_11_comments': {'total': comments_total, 'hidden_share': round(comments_hidden / comments_total, 3) if comments_total else None,
                           'held_share': round(comments_held / comments_total, 3) if comments_total else None},
        'pins_week': pins_week, 'ratings_week': ratings_week,
        'accounts_total': Spina3Profile.objects.count(),
    }
    out['alarms'] = alarms(out)
    return out


def alarms(metrics: dict) -> list[str]:
    out = []
    if metrics['m4_3_top20_group_share'] > 0.60:
        out.append('4.3: ponad 60% top-20 to jedna partia: przełącz domyślny widok na Najnowsze lub Spór (decyzja człowieka).')
    accounts = metrics['m4_7_accounts'] or {}
    clusters = accounts.get('cluster_share')
    if (clusters is not None and clusters > 0.10) or metrics['m4_9_level_changes_per_100_ratings_n_gt_10'] > 5:
        out.append('4.7/4.9: klastry > 10% albo niestabilne poziomy: zamrożenie zmian poziomu na 24 h (level_step_per_day=0), przegląd kont.')
    young = accounts.get('young_share')
    if young is not None and metrics['ratings_week'] >= 50 and young > 0.50:
        out.append('4.7: ponad połowa ocen z kont młodszych niż 7 dni (brigading): ratings_enabled=false dla T1 albo zasłona kalibracyjna.')
    median = (metrics['m4_8_moderation'] or {}).get('median_decision_hours')
    if median is not None and median > 48:
        out.append('4.8: mediana decyzji > 48 h: url_pins_enabled=false i comments_enabled=false do czasu rozładowania kolejki.')
    stances = metrics['m4_5_stances']
    total = sum(stances.values())
    if total >= 50 and min(stances.values()) / total < 0.05:
        out.append('4.5: jedna z ocen poniżej 5%: sprawdź, czy przypięcia nie są jednostronne (autor jako jedyny dowód).')
    comments = metrics['m4_11_comments'] or {}
    if (comments.get('hidden_share') or 0) > 0.10 and comments.get('total', 0) >= 50:
        out.append('4.11: ponad 10% komentarzy ukrytych: wzmocnij pre-filtr albo wstrzymaj komentarze z kont T1.')
    return out
