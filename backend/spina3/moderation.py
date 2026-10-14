"""Moderacja i zgłoszenia (etap G, v2): kolejka z SLA, uzasadnienie decyzji (DSA art. 17), jedna apelacja na decyzję.

Zgłasza się przypięcie, box albo komentarz (oceny nie mają treści, więc nie podlegają zgłoszeniu). SLA: "dane osoby
prywatnej", "groźba" i "osoba, której dotyczy wpis" 24 h; reszta 72 h. Żadnego cichego ukrywania: każda akcja ograniczająca
treść albo konto zapisuje ModerationDecision (fakty, podstawa, automat, kto, droga odwołania) i wysyła ją autorowi e-mailem
(spina3.legal). Sankcje stopniowane: ukrycie treści, waga 0 na 30 dni, zawieszenie (zawsze osobną decyzją wobec konta).
Odwołanie: jedno na decyzję, 6 miesięcy (DSA art. 20).
"""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from . import events, legal
from .comments import hide_comment, restore_comment
from .config import config
from .models import Appeal, Box, Comment, Correction, ModerationDecision, Pin, Report, Spina3Profile
from .spinka import recompute


class ModerationError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def sla_for(reason: str) -> timedelta:
    return timedelta(hours=24) if reason in Report.URGENT else timedelta(hours=72)


@transaction.atomic
def report(user, *, pin: Pin | None = None, box: Box | None = None, comment: Comment | None = None, reason: str,
           details: str = '', name: str = '', email: str = '', good_faith: bool = False,
           location: str = '', explanation: str = '', now=None) -> Report:
    now = now or timezone.now()
    if sum(1 for t in (pin, box, comment) if t is not None) != 1:
        raise ModerationError(400, 'Zgłoszenie dotyczy przypięcia, boxa albo komentarza.')
    if reason not in dict(Report.REASONS):
        raise ModerationError(400, 'Nieznana kategoria zgłoszenia.')
    if Report.objects.filter(reporter=user, created_at__gte=now - timedelta(days=1)).count() >= config().reports_per_day:
        raise ModerationError(429, 'Limit zgłoszeń na dobę został wyczerpany.')
    own = (pin is not None and pin.user_id == getattr(user, 'pk', None)) or (comment is not None and comment.user_id == getattr(user, 'pk', None))
    if own:
        raise ModerationError(400, 'Własną treść można edytować albo usunąć, nie zgłaszać.')
    if Report.objects.filter(reporter=user, pin=pin, box=box, comment=comment).exists():
        raise ModerationError(409, 'To zgłoszenie już istnieje.')
    row = Report.objects.create(reporter=user, pin=pin, box=box, comment=comment, reason=reason, details=(details or '')[:500],
                                name=name, email=email, good_faith=good_faith, location=location, explanation=explanation,
                                sla_deadline=now + sla_for(reason), created_at=now)
    events.log('reported', row.target_box, pin=pin, actor=events.pseudonym(user),
               meta={'reason': reason, 'comment_id': comment.pk if comment else None}, now=now)
    return row


@transaction.atomic
def hide_pin(pin: Pin, staff, reason: str, now=None, *, sanction: str = '', basis: str = '', report: Report | None = None,
             automated: bool = False) -> Pin:
    now = now or timezone.now()
    if pin.status == 'hidden':
        return pin
    pin.status, pin.hidden_reason = 'hidden', (reason or 'Ukryte przez zespół spina3.')[:240]
    pin.save(update_fields=['status', 'hidden_reason', 'updated_at'])
    if pin.user_id:
        profile = Spina3Profile.for_user(pin.user)
        profile.hidden_count += 1
        profile.save(update_fields=['hidden_count'])
        if not profile.is_system:
            legal.record_decision(user=pin.user, target_type='pin', restriction='hide', facts=pin.hidden_reason, basis=basis,
                                  staff=staff, pin=pin, box=pin.box, report=report, automated=automated, now=now)
            legal.apply_sanction(pin.user, staff, sanction, pin.hidden_reason, basis=basis, report=report, now=now)
    events.log('hidden', pin.box, pin=pin, actor=events.pseudonym(pin.user) if pin.user_id else '',
               meta={'by': 'moderation', 'reason': pin.hidden_reason, 'staff': staff.pk if staff else None}, now=now)
    recompute(pin.box, now)
    return pin


@transaction.atomic
def restore_pin(pin: Pin, staff, reason: str = '', now=None) -> Pin:
    now = now or timezone.now()
    if pin.status != 'hidden':
        return pin
    pin.status, pin.hidden_reason = 'published', ''
    pin.save(update_fields=['status', 'hidden_reason', 'updated_at'])
    legal.revoke_decisions(pin=pin, now=now)
    if pin.user_id:
        profile = Spina3Profile.for_user(pin.user)
        profile.hidden_count = max(0, profile.hidden_count - 1)
        profile.save(update_fields=['hidden_count'])
    events.log('restored', pin.box, pin=pin, meta={'by': 'moderation', 'reason': reason, 'staff': staff.pk if staff else None}, now=now)
    recompute(pin.box, now)
    return pin


def _box_owner(box: Box):
    """Autor boxa, którego dotyczy decyzja: użytkownik, który go dodał, a dla boxa bez autora: autor jedynego przypięcia."""
    if box.added_by == 'user' and box.added_by_user_id:
        return box.added_by_user
    pin = Pin.objects.filter(box=box).exclude(status='removed').exclude(kind='diagnosis').select_related('user').first()
    return pin.user if pin and pin.user_id else None


@transaction.atomic
def hide_box(box: Box, staff, reason: str, now=None, *, basis: str = '', report: Report | None = None, automated: bool = False) -> Box:
    """Box ukryty jako KOTWICA: przypięcie i komentarze znikają razem z nim, S zamrożone; jako CEL: 7 dni na wymianę."""
    from .pins import mark_target_unavailable
    now = now or timezone.now()
    box.status, box.hidden_reason = 'hidden', (reason or '')[:240]
    box.save(update_fields=['status', 'hidden_reason', 'updated_at'])
    legal.record_decision(user=_box_owner(box), target_type='box', restriction='hide', facts=reason or 'Box ukryty przez zespół spina3.',
                          basis=basis, staff=staff, box=box, report=report, automated=automated, now=now)
    events.log('system', box, meta={'hidden': True, 'reason': reason, 'staff': staff.pk if staff else None}, now=now)
    recompute(box, now)
    mark_target_unavailable(box, now)
    return box


@transaction.atomic
def restore_box(box: Box, staff, now=None) -> Box:
    from .pins import restore_target
    now = now or timezone.now()
    box.status, box.hidden_reason = 'published', ''
    box.save(update_fields=['status', 'hidden_reason', 'updated_at'])
    legal.revoke_decisions(box=box, now=now)
    recompute(box, now)
    restore_target(box, now)
    return box


@transaction.atomic
def withdraw_box(box: Box, staff, reason: str, now=None) -> Box:
    """Wycofanie na żądanie (np. art. 17 RODO): treść ukryta, S zamrożone, przypięcia pokazują "materiał niedostępny"."""
    from .pins import mark_target_unavailable
    now = now or timezone.now()
    box.source_status, box.text, box.quote, box.thumbnail_url = 'withdrawn', '', '', ''
    box.save()
    legal.record_decision(user=_box_owner(box), target_type='box', restriction='remove', facts=reason or 'Materiał wycofany na żądanie.',
                          basis=legal.PRZEPIS_RODO_ART_17, staff=staff, box=box, now=now)
    events.log('system', box, meta={'withdrawn': True, 'reason': reason}, now=now)
    recompute(box, now)
    mark_target_unavailable(box, now)
    return box


@transaction.atomic
def decide_report(row: Report, staff, decision: str, reason: str, now=None, *, sanction: str = '', basis: str = '') -> Report:
    now = now or timezone.now()
    if row.status != 'new':
        raise ModerationError(409, 'To zgłoszenie ma już decyzję.')
    if decision not in ('hide', 'dismiss'):
        raise ModerationError(400, 'Decyzja: hide albo dismiss.')
    if not (reason or '').strip():
        raise ModerationError(400, 'Decyzja wymaga uzasadnienia (DSA art. 17).')
    row.status = 'hidden' if decision == 'hide' else 'dismissed'
    row.reviewed_by, row.reviewed_at, row.decision_reason = staff, now, reason[:600]
    row.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'decision_reason'])
    if decision == 'hide':
        basis = basis or legal.REPORT_BASIS.get(row.reason, '')
        if row.pin_id:
            hide_pin(row.pin, staff, reason, now, sanction=sanction, basis=basis, report=row)
        elif row.comment_id:
            hide_comment(row.comment, staff, reason, now, sanction=sanction, basis=basis, report=row)
        else:
            hide_box(row.box, staff, reason, now, basis=basis, report=row)
    return row


@transaction.atomic
def suspend_account(user, staff, reason: str, *, basis: str = '', days: int = 30, now=None) -> ModerationDecision:
    """Zawieszenie konta: wyłącznie przez decyzję z uzasadnieniem (DSA art. 17)."""
    if not (reason or '').strip():
        raise ModerationError(400, 'Decyzja wymaga uzasadnienia (DSA art. 17).')
    return legal.apply_sanction(user, staff, 'suspend_30d', reason, basis=basis, now=now, days=days)


@transaction.atomic
def appeal(user, *, pin: Pin | None = None, comment: Comment | None = None, text: str, now=None) -> Appeal:
    now = now or timezone.now()
    target = pin if pin is not None else comment
    if target is None or (pin is not None and comment is not None):
        raise ModerationError(400, 'Odwołanie dotyczy przypięcia albo komentarza.')
    if target.user_id != getattr(user, 'pk', None):
        raise ModerationError(403, 'Odwołać się może tylko autor treści.')
    if target.status != 'hidden':
        raise ModerationError(409, 'Odwołanie dotyczy tylko ukrytej treści.')
    decision = legal.latest_open_decision(pin=pin, comment=comment)
    deadline = decision.appeal_deadline if decision else legal.add_months(target.updated_at, legal.APPEAL_MONTHS)
    if now > deadline:
        raise ModerationError(409, 'Czas na odwołanie (6 miesięcy) minął.')
    if Appeal.objects.filter(pin=pin, comment=comment, author=user).exists() or (
            decision is not None and Appeal.objects.filter(decision=decision).exists()):
        raise ModerationError(409, 'Jedno odwołanie na decyzję.')
    return Appeal.objects.create(pin=pin, comment=comment, decision=decision, author=user, text=(text or '')[:1000], created_at=now)


@transaction.atomic
def appeal_decision(user, decision: ModerationDecision, text: str, now=None) -> Appeal:
    """Odwołanie od decyzji z dziennika (me/decisions/{id}/appeal/): tylko adresat, jedno na decyzję, 6 miesięcy."""
    now = now or timezone.now()
    if decision.user_id != getattr(user, 'pk', None):
        raise ModerationError(404, 'Nie ma takiej decyzji.')
    if not (text or '').strip():
        raise ModerationError(400, 'Odwołanie wymaga treści.')
    if Appeal.objects.filter(decision=decision).exists():
        raise ModerationError(409, 'Jedno odwołanie na decyzję.')
    if decision.revoked_at is not None:
        raise ModerationError(409, 'Decyzja została już uchylona.')
    if now > decision.appeal_deadline:
        raise ModerationError(409, 'Czas na odwołanie (6 miesięcy) minął.')
    return Appeal.objects.create(decision=decision, author=user, text=text.strip()[:1000], created_at=now)


@transaction.atomic
def decide_appeal(row: Appeal, staff, decision: str, reason: str, now=None) -> Appeal:
    now = now or timezone.now()
    if row.status != 'open':
        raise ModerationError(409, 'To odwołanie ma już decyzję.')
    if decision not in ('accept', 'reject') or not (reason or '').strip():
        raise ModerationError(400, 'Decyzja (accept|reject) z uzasadnieniem.')
    row.status, row.decided_by, row.decided_at, row.decision_reason = ('accepted' if decision == 'accept' else 'rejected'), staff, now, reason[:600]
    row.save(update_fields=['status', 'decided_by', 'decided_at', 'decision_reason'])
    if decision == 'accept':
        target = row.decision
        if row.pin_id:
            restore_pin(row.pin, staff, reason, now)
        elif row.comment_id:
            restore_comment(row.comment, staff, reason, now)
        elif target is not None and target.target_type == 'account':
            legal.lift_sanction(target, now)
        elif target is not None and target.target_type == 'pin' and target.pin_id:
            restore_pin(target.pin, staff, reason, now)
        elif target is not None and target.target_type == 'comment' and target.comment_id:
            restore_comment(target.comment, staff, reason, now)
        elif target is not None and target.target_type == 'box' and target.box_id and target.restriction == 'hide':
            restore_box(target.box, staff, now)
        if target is not None and target.revoked_at is None:
            target.revoked_at = now
            target.save(update_fields=['revoked_at'])
    return row


def queue(now=None) -> dict:
    now = now or timezone.now()
    reports = Report.objects.filter(status='new').select_related('pin', 'box', 'comment').order_by('sla_deadline')
    appeals = Appeal.objects.filter(status='open').select_related('pin', 'comment', 'decision').order_by('created_at')
    corrections = Correction.objects.filter(status='pending').order_by('due_at')
    from .models import UrlCheck
    urls = UrlCheck.objects.filter(status__in=('queued', 'needs_review')).order_by('created_at')
    held = Comment.objects.filter(status='held').order_by('created_at')
    review = Comment.objects.filter(needs_review=True).exclude(status='removed').order_by('updated_at')
    pending_boxes = Box.objects.filter(status='pending').order_by('created_at')
    return {
        'reports': [{'id': r.pk, 'reason': r.reason, 'details': r.details, 'pin_id': r.pin_id, 'box_id': r.box_id, 'comment_id': r.comment_id,
                     'sla_deadline': r.sla_deadline.isoformat() if r.sla_deadline else None,
                     'overdue': bool(r.sla_deadline and r.sla_deadline < now), 'created_at': r.created_at.isoformat()} for r in reports[:200]],
        'appeals': [{'id': a.pk, 'pin_id': a.pin_id, 'comment_id': a.comment_id, 'decision_id': a.decision_id,
                     'target_type': a.decision.target_type if a.decision_id else ('pin' if a.pin_id else 'comment'),
                     'text': a.text, 'created_at': a.created_at.isoformat(),
                     'deadline': (a.created_at + timedelta(days=14)).isoformat()} for a in appeals[:200]],
        'corrections': [{'id': c.pk, 'box_id': c.box_id, 'text': c.text, 'name': c.name, 'email': c.email,
                         'consent_public_name': c.consent_public_name, 'due_at': c.due_at.isoformat(), 'overdue': c.due_at < now,
                         'created_at': c.created_at.isoformat()} for c in corrections[:200]],
        'urls': [{'id': u.pk, 'url': u.url_normalized, 'status': u.status, 'reason': u.reason, 'checks': u.checks,
                  'fetched': u.fetched, 'box_id': u.box_id, 'created_at': u.created_at.isoformat()} for u in urls[:200]],
        'held_comments': [{'id': c.pk, 'box_id': c.box_id, 'text': c.text, 'created_at': c.created_at.isoformat()} for c in held[:200]],
        'review_comments': [{'id': c.pk, 'box_id': c.box_id, 'text': c.text, 'status': c.status, 'reason': 'consent_withdrawn',
                             'created_at': c.created_at.isoformat()} for c in review[:200]],
        'pending_boxes': [{'id': b.pk, 'title': b.title, 'url': b.url, 'created_at': b.created_at.isoformat()} for b in pending_boxes[:200]],
        'counts': {'reports': reports.count(), 'appeals': appeals.count(), 'urls': urls.count(), 'held_comments': held.count(),
                   'pending_boxes': pending_boxes.count(), 'corrections': corrections.count(),
                   'review_comments': review.count()},
    }
