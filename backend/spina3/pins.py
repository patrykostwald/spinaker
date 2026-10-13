"""Reguły zapisu v2: box autora z DOKŁADNIE JEDNYM przypięciem (jedna transakcja), edycja i usunięcie przypięcia,
rzecz, która zniknęła, anonimizacja konta, zwolnienie wstrzymanych po ciszy wyborczej.

Box (kotwica) może być: adresem URL spoza bazy (nowy box, czeka na decyzję człowieka; T3 od razu widoczny), zdjęciem
(zarezerwowane, 403) albo boxem z bazy (box importera bez przypięcia "przejmuje" pierwszy użytkownik; cudzego boxa
użytkownika nie da się przejąć). Przypięcie (dowód) to URL, zdjęcie albo box z bazy, z komentarzem autora.

Kody błędów (PinError.status): 400 dane, 403 brak uprawnień lub flaga, 404 brak boxa, 409 konflikt
(box ma już przypięcie, przypięcie do samego siebie, box wycofany), 423 cisza wyborcza, 429 limit.
"""
from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlsplit

from django.db import transaction
from django.utils import timezone

from . import events, url_queue
from .comment_filter import check_comment
from .config import AUTHOR_STANCES, config, election_silence, flags
from .models import Box, Comment, HeldPublication, Pin, Rating, Spina3Profile
from .spinka import recompute
from .text import normalize
from .trust import trust_for


class PinError(Exception):
    def __init__(self, status: int, detail: str, code: str = ''):
        super().__init__(detail)
        self.status, self.detail, self.code = status, detail, code


def parse_author_stance(value) -> int | None:
    """Stanowisko autora wobec treści boxa: opcjonalne (agree | doubt | disagree albo 1 | 0 | -1)."""
    if value is None or value == '':
        return None
    if isinstance(value, str) and value in AUTHOR_STANCES:
        return AUTHOR_STANCES[value]
    if value in (-1, 0, 1):
        return int(value)
    raise PinError(400, 'Stanowisko autora: zgadzam się (+1), mam wątpliwości (0), nie zgadzam się (-1) albo brak.', 'stance')


def _check_flags(now):
    fl = flags()
    if not fl.enabled or not fl.pins_enabled:
        raise PinError(403, 'Dodawanie boxów z przypięciem jest wyłączone.', 'pins_disabled')
    silence = election_silence(now)
    if silence['user_pins_paused']:
        raise PinError(423, 'Cisza wyborcza: boxy i przypięcia użytkowników publikujemy po jej zakończeniu.', 'election_silence')


def _check_box(box: Box):
    if box.status != 'published':
        raise PinError(404, 'Nie ma takiego boxa.', 'box')
    if box.source_status != 'active':
        raise PinError(409, 'Materiał wycofany u źródła: nowe przypięcia są zablokowane, ocena zamrożona.', 'frozen')


def _check_limits(actor: str, trust, now, cfg):
    created = events.count_recent(actor, ('created', 'replaced'), 24, now)
    if created >= trust.daily_limit:
        raise PinError(429, f'Limit {trust.daily_limit} boxów z przypięciem na dobę dla tego konta.', 'daily_limit')
    burst = events.count_recent(actor, ('created',), cfg.burst_window_seconds / 3600, now)
    if burst >= cfg.burst_max_pins:
        raise PinError(429, 'Za szybko: odczekaj chwilę przed kolejnym przypięciem.', 'burst')


def _check_same_target(user, target_box: Box | None, trust, now, cfg):
    if target_box is None:
        return
    limit = cfg.same_target_30d.get(trust.tier, cfg.same_target_30d['T2'])
    since = now - timedelta(days=30)
    count = Pin.objects.filter(user=user, pinned_box=target_box, created_at__gte=since).exclude(status='removed').count()
    if count >= limit:
        raise PinError(429, f'Tę rzecz można przypiąć najwyżej {limit} razy na 30 dni.', 'same_target')


def _check_url_quota(user, normalized: str, now, cfg):
    pending = Pin.objects.filter(user=user, target_status='pending').exclude(status='removed').count()
    pending += Box.objects.filter(added_by_user=user, status='pending').count()
    if pending >= cfg.url_pending_per_account:
        raise PinError(429, 'Masz już adres w kolejce weryfikacji; poczekaj na decyzję.', 'url_pending')
    domain = urlsplit(normalized).hostname or ''
    if url_queue.domain_submissions_today(domain, now) >= cfg.url_per_domain_per_day:
        raise PinError(429, 'Limit adresów z tej domeny na dobę został wyczerpany.', 'url_domain')


def _normalized_url(target, trust):
    fl = flags()
    if not fl.url_pins_enabled:
        raise PinError(403, 'Adresy spoza bazy są wyłączone.', 'url_disabled')
    if not trust.can_pin_url:
        raise PinError(403, 'Adresy spoza bazy może dodawać konto po 14 dniach i 5 aktywnościach.', 'url_tier')
    normalized = url_queue.normalize_url(str(target or ''))
    if not normalized:
        raise PinError(400, 'Podaj poprawny adres http(s).', 'url')
    return normalized


def _resolve_target(user, box: Box, kind: str, target, trust, actor: str, now, cfg):
    """Dowód przypięcia. Zwraca (kind, pinned_box, url, url_check, target_status, info)."""
    fl = flags()
    if kind == 'image':
        if not fl.allow_image_pins:
            raise PinError(403, 'Przypięcia zdjęć są wyłączone (ALLOW_IMAGE_PINS=false).', 'image_disabled')
        raise PinError(403, 'Przypięcia zdjęć wymagają moderacji przed publikacją; kolejka nie jest jeszcze uruchomiona.', 'image_queue')
    if kind == 'box':
        try:
            target_box = Box.objects.get(pk=int(target))
        except (Box.DoesNotExist, TypeError, ValueError):
            raise PinError(404, 'Nie ma takiego boxa do przypięcia.', 'target')
        return _box_target(box, target_box, user, trust, now, cfg)
    if kind == 'url':
        normalized = _normalized_url(target, trust)
        existing = Box.objects.filter(url=normalized).first()
        if existing is not None:
            kind_, pinned, url_, check_, status_, info = _box_target(box, existing, user, trust, now, cfg)
            return kind_, pinned, url_, check_, status_, {'message': f'To już jest w bazie: {existing.title}', 'box_id': existing.pk}
        _check_url_quota(user, normalized, now, cfg)
        check = url_queue.enqueue(normalized, actor, now)
        if check.status == 'rejected':
            raise PinError(400, check.reason or 'Adres odrzucony.', 'url_rejected')
        return 'url', None, normalized, check, 'pending', {'message': 'Sprawdzimy ten adres; karta linku pokaże się po weryfikacji.'}
    raise PinError(400, 'Rodzaj przypięcia: box, url albo image.', 'kind')


def _box_target(box, target_box, user, trust, now, cfg):
    if target_box.pk == box.pk:
        raise PinError(409, 'Box nie może być przypięty do samego siebie.', 'self')
    if target_box.status != 'published':
        raise PinError(404, 'Nie ma takiego boxa do przypięcia.', 'target')
    if not target_box.pinnable_as_target or not target_box.public_function:
        raise PinError(403, 'Materiał niedostępny do przypinania.', 'not_pinnable')
    _check_same_target(user, target_box, trust, now, cfg)
    status = 'ok' if target_box.source_status == 'active' else 'unavailable'
    return 'box', target_box, '', None, status, {}


def _apply_comment(pin: Pin, comment: str, cfg):
    check = check_comment(comment, cfg.comment_max)
    if check.status == 'blocked':
        raise PinError(400, check.reason, 'comment')
    pin.comment = (comment or '').strip()
    pin.comment_status = check.status
    return check


# --- kotwica: box autora -----------------------------------------------------------------------------------

def _existing_box_anchor(user, box: Box) -> Box:
    """Box z bazy jako kotwica: musi być bez przypięcia; cudzego boxa użytkownika nie da się przejąć."""
    _check_box(box)
    if Pin.objects.filter(box=box).exclude(status='removed').exists():
        raise PinError(409, 'Ten box ma już przypięcie autora: oceń je albo skomentuj.', 'has_pin')
    if box.added_by == 'user' and box.added_by_user_id not in (None, user.pk):
        raise PinError(403, 'To box innego użytkownika: tylko autor dodaje przypięcie.', 'not_author')
    if box.added_by == 'dr_spin' and box.kind == 'post':
        raise PinError(403, 'Wpis polityka czeka na diagnozę Dr. Spina: to ona jest jedynym przypięciem; oceń ją po publikacji.',
                       'reserved_for_diagnosis')
    if box.added_by != 'user' and not flags().adopt_authorless_boxes:
        raise PinError(403, 'Boxy importera przypina tylko zespół (adopt_authorless_boxes=false).', 'adopt_disabled')
    return box


def _resolve_anchor(user, kind: str, target, title: str, box_kind: str, trust, actor: str, now, cfg) -> tuple[Box, bool, dict]:
    """Zwraca (box, utworzony?, info)."""
    if kind == 'image':
        if not flags().allow_image_pins:
            raise PinError(403, 'Boxy ze zdjęć są wyłączone (ALLOW_IMAGE_PINS=false).', 'image_disabled')
        raise PinError(403, 'Boxy ze zdjęć wymagają moderacji przed publikacją; kolejka nie jest jeszcze uruchomiona.', 'image_queue')
    if kind == 'box':
        try:
            box = Box.objects.select_for_update().get(pk=int(target))
        except (Box.DoesNotExist, TypeError, ValueError):
            raise PinError(404, 'Nie ma takiego boxa.', 'box')
        return _existing_box_anchor(user, box), False, {}
    if kind == 'url':
        normalized = _normalized_url(target, trust)
        existing = Box.objects.select_for_update().filter(url=normalized).first()
        if existing is not None:
            return _existing_box_anchor(user, existing), False, {'message': f'To już jest w bazie: {existing.title}', 'box_id': existing.pk}
        _check_url_quota(user, normalized, now, cfg)
        check = url_queue.enqueue(normalized, actor, now)
        if check.status == 'rejected':
            raise PinError(400, check.reason or 'Adres odrzucony.', 'url_rejected')
        domain = urlsplit(normalized).hostname or ''
        status = 'published' if trust.tier == 'T3' else 'pending'
        box = Box.objects.create(
            kind=box_kind if box_kind in ('article', 'video', 'document', 'post') else 'article',
            title=(title or '').strip()[:500] or normalized, url=normalized, source_name=domain, source_domain=domain,
            added_by='user', added_by_user=user, reader_link=True, noindex=True, show_title=True, show_quote=False,
            show_thumbnail=False, show_avatar=False, published_at=now, created_at=now, status=status,
            search_text=normalize(title or domain))
        if check.box_id is None:
            check.box = box
            check.save(update_fields=['box'])
        info = {'message': 'Box czeka na sprawdzenie adresu; pokaże się po decyzji zespołu.'} if status == 'pending' else {}
        return box, True, info
    raise PinError(400, 'Rodzaj boxa: box, url albo image.', 'box_kind')


@transaction.atomic
def create_box_with_pin(user, *, box_kind: str = 'box', box_target=None, box_title: str = '', box_type: str = 'article',
                        pin_kind: str = 'box', pin_target=None, comment: str = '', stance=None, now=None) -> tuple[Box, Pin, dict]:
    """Jedna operacja: kotwica (box) + jedyne przypięcie autora. Zwraca (box, pin, info ze spinką)."""
    now = now or timezone.now()
    cfg = config()
    _check_flags(now)
    trust = trust_for(user, cfg, now)
    if not trust.can_publish:
        raise PinError(403, 'To konto nie może publikować: ' + (trust.reason or 'potwierdź e-mail.'), 'tier')
    profile = Spina3Profile.for_user(user)
    if profile.consent_art9_at is None and not trust.is_team:
        raise PinError(403, 'Przed pierwszą publikacją potrzebna jest zgoda na publikację stanowisk przy nicku.', 'consent')
    actor = profile.pseudonym
    stance_value = parse_author_stance(stance)
    _check_limits(actor, trust, now, cfg)
    box, created_box, info = _resolve_anchor(user, box_kind, box_target, box_title, box_type, trust, actor, now, cfg)
    kind_, pinned, url_, check_, target_status, extra = _resolve_target(user, box, pin_kind, pin_target, trust, actor, now, cfg)
    pin = Pin(user=user, box=box)
    pin.kind, pin.pinned_box, pin.url, pin.url_check, pin.target_status = kind_, pinned, url_, check_, target_status
    pin.stance, pin.status, pin.is_team = stance_value, 'published', trust.is_team
    pin.created_at, pin.hidden_reason, pin.anonymized = now, '', False
    pin.unavailable_since = now if target_status == 'unavailable' else None
    pin.replace_deadline = now + timedelta(days=cfg.replace_days) if target_status == 'unavailable' else None
    comment_check = _apply_comment(pin, comment, cfg)
    silence = election_silence(now)
    if silence['active'] and trust.is_team:
        pin.status, pin.held_until = 'held', _parse_end(silence)
    pin.save()
    if pin.status == 'held':
        HeldPublication.objects.get_or_create(kind='pin', object_id=pin.pk, defaults={'release_at': pin.held_until})
    events.log('created', box, pin=pin, actor=actor, after=stance_value,
               meta={'kind': kind_, 'target_status': target_status, 'tier': trust.tier, 'box_created': created_box,
                     'box_status': box.status}, now=now)
    sp = recompute(box, now, cfg)
    info = {**info, **extra}
    if comment_check.status == 'held':
        info['comment'] = comment_check.reason
    return box, pin, {'spinka': sp, **info}


def _parse_end(silence: dict):
    from django.utils.dateparse import parse_datetime
    return parse_datetime(silence['ends_at']) if silence.get('ends_at') else None


@transaction.atomic
def update_pin(user, pin: Pin, *, stance=None, comment=None, kind: str | None = None, target=None, now=None) -> tuple[Pin, dict]:
    now = now or timezone.now()
    cfg = config()
    _check_flags(now)
    if pin.user_id != getattr(user, 'pk', None) or pin.kind == 'diagnosis':
        raise PinError(403, 'To nie jest Twoje przypięcie.', 'owner')
    if pin.status in ('removed',):
        raise PinError(404, 'Przypięcie zostało usunięte.', 'removed')
    if pin.status == 'hidden':
        raise PinError(409, 'Przypięcie ukryte przez moderację: możesz się odwołać, nie edytować.', 'hidden')
    if pin.box.status == 'published':
        _check_box(pin.box)
    trust = trust_for(user, cfg, now)
    actor = Spina3Profile.for_user(user).pseudonym
    info: dict = {}
    if stance is not None:
        new_stance = parse_author_stance(stance)
        if new_stance != pin.stance:
            last = pin.stance_changed_at or pin.created_at
            if now < last + timedelta(hours=cfg.stance_edit_cooldown_hours):
                raise PinError(429, 'Stanowisko autora można zmienić raz na 24 godziny.', 'stance_cooldown')
            events.log('stance_changed', pin.box, pin=pin, actor=actor, before=pin.stance, after=new_stance, now=now)
            pin.stance, pin.stance_changed_at = new_stance, now
    if comment is not None:
        check = _apply_comment(pin, comment, cfg)
        if check.status == 'held':
            info['comment'] = check.reason
        events.log('edited', pin.box, pin=pin, actor=actor, now=now)
    if kind is not None or target is not None:
        kind_, pinned, url_, check_, target_status, extra = _resolve_target(user, pin.box, kind or pin.kind, target, trust, actor, now, cfg)
        pin.kind, pin.pinned_box, pin.url, pin.url_check, pin.target_status = kind_, pinned, url_, check_, target_status
        pin.unavailable_since = now if target_status == 'unavailable' else None
        pin.replace_deadline = now + timedelta(days=cfg.replace_days) if target_status == 'unavailable' else None
        info.update(extra)
        events.log('replaced', pin.box, pin=pin, actor=actor, meta={'kind': kind_, 'target_status': target_status}, now=now)
    pin.save()
    sp = recompute(pin.box, now, cfg)
    return pin, {'spinka': sp, **info}


@transaction.atomic
def remove_pin(user, pin: Pin, now=None) -> None:
    """Autor usuwa swoje przypięcie: zwalnia miejsce przy boxie; box dodany przez autora znika ze ściany (ukryty),
    oceny zostają w bazie, ale nie liczą się (spinka Otwarta: brak przypięcia)."""
    now = now or timezone.now()
    if pin.user_id != getattr(user, 'pk', None) or pin.kind == 'diagnosis':
        raise PinError(403, 'To nie jest Twoje przypięcie.', 'owner')
    if pin.status == 'removed':
        return
    actor = Spina3Profile.for_user(user).pseudonym
    pin.status = 'removed'
    pin.save(update_fields=['status', 'updated_at'])
    events.log('removed', pin.box, pin=pin, actor=actor, before=pin.stance, meta={'ratings': pin.ratings.count()}, now=now)
    box = pin.box
    if box.added_by == 'user' and box.added_by_user_id == user.pk and box.status in ('published', 'pending'):
        box.status, box.hidden_reason = 'hidden', 'autor usunął przypięcie'
        box.save(update_fields=['status', 'hidden_reason', 'updated_at'])
        mark_target_unavailable(box, now)
    recompute(box, now)


# --- rzecz, która zniknęła ---------------------------------------------------------------------------------

@transaction.atomic
def mark_target_unavailable(target: Box, now=None) -> int:
    """Box ukryty, wycofany albo usunięty u źródła jako CEL: przypięcie zostaje, karta "materiał niedostępny", oceny nie
    liczą się (spinka Otwarta: dowód niedostępny), autor ma 7 dni na wymianę, potem przypięcie ukryte."""
    now = now or timezone.now()
    cfg = config()
    boxes: set[int] = set()
    for pin in Pin.objects.filter(pinned_box=target, status='published', target_status='ok'):
        pin.target_status, pin.unavailable_since = 'unavailable', now
        pin.replace_deadline = now + timedelta(days=cfg.replace_days)
        pin.save(update_fields=['target_status', 'unavailable_since', 'replace_deadline', 'updated_at'])
        events.log('target_unavailable', pin.box, pin=pin, actor=pseudonym_of(pin), now=now)
        boxes.add(pin.box_id)
    for box in Box.objects.filter(pk__in=boxes):
        recompute(box, now)
    return len(boxes)


@transaction.atomic
def restore_target(target: Box, now=None) -> int:
    """Przywrócenie celu w czasie na wymianę przywraca przypięcia automatycznie."""
    now = now or timezone.now()
    boxes: set[int] = set()
    for pin in Pin.objects.filter(pinned_box=target, status__in=('published', 'hidden'), target_status='unavailable'):
        pin.target_status, pin.unavailable_since, pin.replace_deadline = 'ok', None, None
        if pin.status == 'hidden' and pin.hidden_reason.startswith('materiał niedostępny'):
            pin.status, pin.hidden_reason = 'published', ''
        pin.save(update_fields=['target_status', 'unavailable_since', 'replace_deadline', 'status', 'hidden_reason', 'updated_at'])
        events.log('restored', pin.box, pin=pin, actor=pseudonym_of(pin), now=now)
        boxes.add(pin.box_id)
    for box in Box.objects.filter(pk__in=boxes):
        recompute(box, now)
    return len(boxes)


@transaction.atomic
def expire_unavailable(now=None) -> int:
    """Po 7 dniach bez wymiany przypięcie jest ukryte (zadanie okresowe)."""
    now = now or timezone.now()
    boxes: set[int] = set()
    rows = Pin.objects.filter(status='published', target_status__in=('unavailable', 'rejected'), replace_deadline__lte=now)
    count = 0
    for pin in rows:
        pin.status, pin.hidden_reason = 'hidden', 'materiał niedostępny: minął czas na wymianę'
        pin.save(update_fields=['status', 'hidden_reason', 'updated_at'])
        events.log('hidden', pin.box, pin=pin, actor=pseudonym_of(pin), meta={'reason': 'replace_deadline'}, now=now)
        boxes.add(pin.box_id)
        count += 1
    for box in Box.objects.filter(pk__in=boxes):
        recompute(box, now)
    return count


def pseudonym_of(pin: Pin) -> str:
    if pin.user_id is None:
        return ''
    return Spina3Profile.for_user(pin.user).pseudonym


@transaction.atomic
def anonymize_user(user, now=None) -> int:
    """Usunięcie konta: przypięcia bez autora i komentarza, oceny bez autora (stanowisko zostaje w agregacie),
    komentarze bez autora i treści; mapowanie pseudonimu znika."""
    now = now or timezone.now()
    boxes: set[int] = set()
    count = 0
    for pin in Pin.objects.filter(user=user):
        pin.user, pin.comment, pin.comment_status, pin.anonymized = None, '', 'empty', True
        pin.save(update_fields=['user', 'comment', 'comment_status', 'anonymized', 'updated_at'])
        boxes.add(pin.box_id)
        count += 1
    for rating in Rating.objects.filter(user=user):
        rating.user, rating.anonymized = None, True
        rating.save(update_fields=['user', 'anonymized', 'updated_at'])
        boxes.add(rating.box_id)
        count += 1
    for comment in Comment.objects.filter(user=user):
        comment.user, comment.anonymized, comment.text = None, True, ''
        if comment.status != 'hidden':
            comment.status = 'removed'
        comment.save(update_fields=['user', 'anonymized', 'text', 'status', 'updated_at'])
        count += 1
    Spina3Profile.objects.filter(user=user).delete()
    for box in Box.objects.filter(pk__in=boxes):
        recompute(box, now)
    return count


def release_held(now=None) -> int:
    """Po ciszy wyborczej: publikuje wstrzymane boxy i przypięcia systemowe (kolejka HeldPublication)."""
    now = now or timezone.now()
    count = 0
    for held in HeldPublication.objects.filter(released_at__isnull=True, release_at__lte=now):
        if held.kind == 'pin':
            pin = Pin.objects.filter(pk=held.object_id, status='held').first()
            if pin is not None:
                pin.status, pin.held_until = 'published', None
                pin.save(update_fields=['status', 'held_until', 'updated_at'])
                events.log('system', pin.box, pin=pin, meta={'released': True}, now=now)
                recompute(pin.box, now)
        else:
            Box.objects.filter(pk=held.object_id, status='held').update(status='published', held_until=None)
        held.released_at = now
        held.save(update_fields=['released_at'])
        count += 1
    return count
