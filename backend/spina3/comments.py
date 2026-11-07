"""Komentarze pod parą box + przypięcie (v2): jeden poziom odpowiedzi, ocena "przydatny", sortowanie (najnowsze /
najlepiej ocenione), kursor, limity i antyspam, zgłoszenia i moderacja z uzasadnieniem (DSA), cisza wyborcza (flaga).

Antyspam: pre-filtr (PESEL = blokada; telefon, e-mail, adres = komentarz czeka na sprawdzenie), konto T1 z linkiem w treści =
czeka na sprawdzenie, limit dobowy wg poziomu, seria 3/min, ten sam tekst pod tym samym boxem w 24 h = 409.
Kody: 400 dane, 403 uprawnienia lub flaga, 404 brak, 409 duplikat albo stan, 423 cisza, 429 limit.
"""
from __future__ import annotations

import re
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from . import events, scoring
from .comment_filter import check_comment
from .config import ScoringConfig, config, election_silence, flags
from .models import Box, Comment, CommentVote, Pin, Spina3Profile
from .pins import PinError
from .trust import trust_for

LINK = re.compile(r'(https?://|www\.)', re.I)
SORTS = ('newest', 'top')


def _check_flags(now):
    fl = flags()
    if not fl.enabled or not fl.comments_enabled:
        raise PinError(403, 'Komentarze są wyłączone.', 'comments_disabled')
    if election_silence(now)['comments_paused']:
        raise PinError(423, 'Cisza wyborcza: komentarze przyjmujemy po jej zakończeniu.', 'election_silence')


def _check_account(user, cfg, now):
    trust = trust_for(user, cfg, now)
    if trust.is_system or not trust.can_publish:
        raise PinError(403, 'To konto nie może komentować: ' + (trust.reason or 'potwierdź e-mail.'), 'tier')
    profile = Spina3Profile.for_user(user)
    if profile.consent_art9_at is None and not trust.is_team:
        raise PinError(403, 'Przed pierwszym komentarzem potrzebna jest zgoda na publikację przy nicku.', 'consent')
    return trust, profile


def _clean_text(text: str, cfg: ScoringConfig) -> tuple[str, str, str]:
    """Zwraca (tekst, status visible|held, powód)."""
    text = re.sub(r'[ \t]+', ' ', (text or '').strip())
    if not text:
        raise PinError(400, 'Komentarz nie może być pusty.', 'text')
    if len(text) > cfg.comment_text_max:
        raise PinError(400, f'Komentarz może mieć najwyżej {cfg.comment_text_max} znaków.', 'text')
    check = check_comment(text, cfg.comment_text_max)
    if check.status == 'blocked':
        raise PinError(400, check.reason, 'text')
    if check.status == 'held':
        return text, 'held', check.reason
    return text, 'visible', ''


@transaction.atomic
def create_comment(user, box: Box, text: str, parent: Comment | None = None, now=None) -> tuple[Comment, dict]:
    now = now or timezone.now()
    cfg = config()
    _check_flags(now)
    if box.status != 'published':
        raise PinError(404, 'Nie ma takiego boxa.', 'box')
    trust, profile = _check_account(user, cfg, now)
    actor = profile.pseudonym
    text, status, reason = _clean_text(text, cfg)
    if status == 'visible' and trust.tier == 'T1' and LINK.search(text):
        status, reason = 'held', 'Komentarz z linkiem z nowego konta czeka na sprawdzenie.'
    if parent is not None:
        if parent.box_id != box.pk or parent.parent_id is not None or parent.status != 'visible':
            raise PinError(400, 'Odpowiedź tylko do widocznego komentarza głównego pod tym boxem.', 'parent')
    daily = events.count_recent(actor, ('commented',), 24, now)
    if daily >= trust.daily_comments:
        raise PinError(429, f'Limit {trust.daily_comments} komentarzy na dobę dla tego konta.', 'daily_limit')
    burst = events.count_recent(actor, ('commented',), cfg.burst_window_seconds / 3600, now)
    if burst >= cfg.burst_max_comments:
        raise PinError(429, 'Za szybko: odczekaj chwilę przed kolejnym komentarzem.', 'burst')
    since = now - timedelta(hours=cfg.comment_duplicate_hours)
    if Comment.objects.filter(user=user, box=box, text=text, created_at__gte=since).exclude(status='removed').exists():
        raise PinError(409, 'Ten sam komentarz już jest pod tym boxem.', 'duplicate')
    pin = Pin.objects.filter(box=box, status='published').first()
    comment = Comment.objects.create(box=box, user=user, parent=parent, text=text, status=status, is_team=trust.is_team,
                                     is_author=bool(pin and pin.user_id == user.pk), created_at=now)
    if parent is not None and status == 'visible':
        Comment.objects.filter(pk=parent.pk).update(reply_count=parent.reply_count + 1)
    events.log('commented', box, actor=actor, meta={'comment_id': comment.pk, 'status': status, 'reply': parent is not None,
                                                     'tier': trust.tier}, now=now)
    info = {'comment_status': status}
    if reason:
        info['message'] = reason
    return comment, info


@transaction.atomic
def edit_comment(user, comment: Comment, text: str, now=None) -> tuple[Comment, dict]:
    now = now or timezone.now()
    cfg = config()
    _check_flags(now)
    if comment.user_id != getattr(user, 'pk', None):
        raise PinError(403, 'To nie jest Twój komentarz.', 'owner')
    if comment.status == 'removed':
        raise PinError(404, 'Komentarz został usunięty.', 'removed')
    if comment.status == 'hidden':
        raise PinError(409, 'Komentarz ukryty przez moderację: możesz się odwołać, nie edytować.', 'hidden')
    text, status, reason = _clean_text(text, cfg)
    trust, profile = _check_account(user, cfg, now)
    if status == 'visible' and trust.tier == 'T1' and LINK.search(text):
        status, reason = 'held', 'Komentarz z linkiem z nowego konta czeka na sprawdzenie.'
    was_visible = comment.status == 'visible'
    comment.text, comment.status, comment.edited_at = text, status, now
    comment.save(update_fields=['text', 'status', 'edited_at', 'updated_at'])
    if comment.parent_id and was_visible != (status == 'visible'):
        _sync_reply_count(comment.parent_id)
    events.log('edited', comment.box, actor=profile.pseudonym, meta={'comment_id': comment.pk}, now=now)
    info = {'comment_status': status}
    if reason:
        info['message'] = reason
    return comment, info


def _sync_reply_count(parent_id: int):
    Comment.objects.filter(pk=parent_id).update(reply_count=Comment.objects.filter(parent_id=parent_id, status='visible').count())


@transaction.atomic
def remove_comment(user, comment: Comment, now=None) -> None:
    now = now or timezone.now()
    if comment.user_id != getattr(user, 'pk', None):
        raise PinError(403, 'To nie jest Twój komentarz.', 'owner')
    if comment.status == 'removed':
        return
    comment.status = 'removed'
    comment.save(update_fields=['status', 'updated_at'])
    if comment.parent_id:
        _sync_reply_count(comment.parent_id)
    events.log('comment_removed', comment.box, actor=Spina3Profile.for_user(user).pseudonym, meta={'comment_id': comment.pk}, now=now)


@transaction.atomic
def vote_helpful(user, comment: Comment, now=None) -> Comment:
    now = now or timezone.now()
    _check_flags(now)
    if comment.status != 'visible':
        raise PinError(404, 'Nie ma takiego komentarza.', 'comment')
    if comment.user_id == getattr(user, 'pk', None):
        raise PinError(403, 'Własnego komentarza nie ocenia się.', 'own')
    trust = trust_for(user, config(), now)
    if trust.is_system or not trust.can_publish:
        raise PinError(403, 'To konto nie może oceniać komentarzy.', 'tier')
    _, created = CommentVote.objects.get_or_create(user=user, comment=comment, defaults={'created_at': now})
    if created:
        comment.helpful_count = CommentVote.objects.filter(comment=comment).count()
        comment.save(update_fields=['helpful_count', 'updated_at'])
    return comment


@transaction.atomic
def unvote_helpful(user, comment: Comment, now=None) -> Comment:
    deleted, _ = CommentVote.objects.filter(user=user, comment=comment).delete()
    if deleted:
        comment.helpful_count = CommentVote.objects.filter(comment=comment).count()
        comment.save(update_fields=['helpful_count', 'updated_at'])
    return comment


# --- moderacja -----------------------------------------------------------------------------------------------

@transaction.atomic
def hide_comment(comment: Comment, staff, reason: str, now=None, *, sanction: str = '') -> Comment:
    now = now or timezone.now()
    if comment.status == 'hidden':
        return comment
    was_visible = comment.status == 'visible'
    comment.status, comment.hidden_reason = 'hidden', (reason or 'Ukryte przez zespół spina3.')[:240]
    comment.save(update_fields=['status', 'hidden_reason', 'updated_at'])
    if comment.user_id:
        profile = Spina3Profile.for_user(comment.user)
        profile.hidden_count += 1
        if sanction == 'weight_zero_30d':
            profile.weight_zero_until = now + timedelta(days=30)
        elif sanction == 'suspend_30d':
            profile.suspended_until = now + timedelta(days=30)
        profile.save(update_fields=['hidden_count', 'weight_zero_until', 'suspended_until'])
    if comment.parent_id and was_visible:
        _sync_reply_count(comment.parent_id)
    events.log('hidden', comment.box, actor=events.pseudonym(comment.user) if comment.user_id else '',
               meta={'by': 'moderation', 'comment_id': comment.pk, 'reason': comment.hidden_reason, 'staff': staff.pk if staff else None}, now=now)
    return comment


@transaction.atomic
def restore_comment(comment: Comment, staff, reason: str = '', now=None) -> Comment:
    """Przywrócenie ukrytego albo zatwierdzenie wstrzymanego (held) komentarza."""
    now = now or timezone.now()
    if comment.status not in ('hidden', 'held'):
        return comment
    was_hidden = comment.status == 'hidden'
    comment.status, comment.hidden_reason = 'visible', ''
    comment.save(update_fields=['status', 'hidden_reason', 'updated_at'])
    if was_hidden and comment.user_id:
        profile = Spina3Profile.for_user(comment.user)
        profile.hidden_count = max(0, profile.hidden_count - 1)
        profile.save(update_fields=['hidden_count'])
    if comment.parent_id:
        _sync_reply_count(comment.parent_id)
    events.log('restored', comment.box, meta={'by': 'moderation', 'comment_id': comment.pk, 'reason': reason,
                                              'staff': staff.pk if staff else None}, now=now)
    return comment


# --- odczyt -----------------------------------------------------------------------------------------------------

def _key(comment: Comment, sort: str) -> tuple:
    ts = comment.created_at.timestamp()
    if sort == 'top':
        return (-comment.helpful_count, -ts, -comment.pk)
    return (-ts, -comment.pk)


def list_comments(box: Box, *, sort: str = 'newest', cursor: str | None = None, limit: int | None = None,
                  viewer=None, cfg: ScoringConfig | None = None) -> dict:
    """Komentarze główne z odpowiedziami (do `comment_replies_limit`), kursor po kluczu sortowania (wersja 0 = bez migawki)."""
    from .public import comment_item
    cfg = cfg or config()
    sort = sort if sort in SORTS else 'newest'
    limit = min(limit or 24, 96)
    viewer_id = getattr(viewer, 'pk', None) if viewer is not None and getattr(viewer, 'is_authenticated', False) else None
    qs = Comment.objects.filter(box=box, parent__isnull=True).select_related('user__spina3_profile')
    visible = qs.filter(status='visible')
    if viewer_id:
        visible = qs.filter(status='visible') | qs.filter(user_id=viewer_id, status__in=('held', 'hidden'))
    rows = list(visible.distinct())
    rows.sort(key=lambda c: _key(c, sort))
    if cursor:
        decoded = scoring.decode_cursor(cursor)
        if decoded is None:
            return {'error': 'Nieprawidłowy kursor.', 'status': 400}
        _, key = decoded
        rows = [c for c in rows if _key(c, sort) > tuple(key)]
    page = rows[:limit]
    has_more = len(rows) > limit
    replies: dict[int, list[Comment]] = {}
    if page:
        reply_qs = Comment.objects.filter(parent__in=page, status='visible').select_related('user__spina3_profile').order_by('created_at', 'pk')
        if viewer_id:
            reply_qs = (Comment.objects.filter(parent__in=page).filter(status='visible')
                        | Comment.objects.filter(parent__in=page, user_id=viewer_id, status__in=('held', 'hidden'))).distinct() \
                .select_related('user__spina3_profile').order_by('created_at', 'pk')
        for reply in reply_qs:
            bucket = replies.setdefault(reply.parent_id, [])
            if len(bucket) < cfg.comment_replies_limit:
                bucket.append(reply)
    voted: set[int] = set()
    if viewer_id:
        ids = [c.pk for c in page] + [r.pk for bucket in replies.values() for r in bucket]
        voted = set(CommentVote.objects.filter(user_id=viewer_id, comment_id__in=ids).values_list('comment_id', flat=True))
    items = [comment_item(c, viewer=viewer, voted=voted, replies=[comment_item(r, viewer=viewer, voted=voted) for r in replies.get(c.pk, [])])
             for c in page]
    return {
        'items': items, 'sort': sort,
        'next_cursor': scoring.encode_cursor(0, _key(page[-1], sort)) if (has_more and page) else None,
        'total': Comment.objects.filter(box=box, status='visible').count(),
    }
