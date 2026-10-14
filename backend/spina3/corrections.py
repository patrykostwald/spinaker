"""Sprostowanie diagnozy (ustawa Prawo prasowe, art. 31a-33): osoba, której dotyczy wpis, składa sprostowanie do 21 dni
od publikacji diagnozy; zespół publikuje je w 3 dni robocze (`due_at`) albo odmawia wyłącznie z powodu z art. 33.

Dane wnioskodawcy (imię i nazwisko, e-mail) służą tylko do obsługi wniosku; publicznie imię i nazwisko wyłącznie za jawną
zgodą (`consent_public_name`), e-mail nigdy. Kody: 400 dane lub termin, 404 box, 409 decyzja już zapadła.
"""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from . import events, legal
from .models import Box, BoxLink, Correction


class CorrectionError(Exception):
    def __init__(self, status: int, detail: str, code: str = ''):
        super().__init__(detail)
        self.status, self.detail, self.code = status, detail, code


def max_length(box: Box) -> int:
    """Do dwukrotnej objętości sprostowywanego materiału (art. 31a ust. 1)."""
    base = len(box.text or box.quote or box.title or '')
    return max(1, base) * legal.CORRECTION_MAX_RATIO


@transaction.atomic
def submit(box: Box, *, name: str, email: str, text: str, statement: bool, consent_public_name: bool = False, now=None) -> Correction:
    now = now or timezone.now()
    if box.kind != 'diagnosis' or box.status != 'published':
        raise CorrectionError(404, 'Sprostowanie dotyczy opublikowanej diagnozy.', 'box')
    if statement is not True:
        raise CorrectionError(400, 'Potwierdź oświadczenie: jestem osobą, której dotyczy wpis, a dane są prawdziwe.', 'statement')
    name, text = (name or '').strip(), (text or '').strip()
    if not name or not text:
        raise CorrectionError(400, 'Imię i nazwisko oraz treść sprostowania są wymagane.', 'required')
    if len(text) > max_length(box):
        raise CorrectionError(400, f'Sprostowanie może mieć najwyżej {max_length(box)} znaków (dwukrotność diagnozy).', 'length')
    published = box.published_at or box.created_at
    if now > published + timedelta(days=legal.CORRECTION_DAYS):
        raise CorrectionError(400, 'Termin na sprostowanie (21 dni od publikacji) minął.', 'deadline')
    row = Correction.objects.create(box=box, name=name[:200], email=email, text=text, statement=True,
                                    consent_public_name=bool(consent_public_name), created_at=now,
                                    due_at=legal.add_working_days(now, legal.CORRECTION_WORKING_DAYS))
    events.log('system', box, meta={'correction': row.pk, 'status': 'pending'}, now=now)
    return row


@transaction.atomic
def decide(row: Correction, staff, decision: str, *, rejection_reason: str = '', note: str = '', now=None) -> Correction:
    now = now or timezone.now()
    if row.status != 'pending':
        raise CorrectionError(409, 'To sprostowanie ma już decyzję.', 'decided')
    if decision == 'publish':
        row.status, row.published_at = 'published', now
    elif decision == 'reject':
        if rejection_reason not in legal.CORRECTION_REJECTIONS:
            raise CorrectionError(400, 'Odmowa wymaga powodu z art. 33 prawa prasowego: ' + ', '.join(legal.CORRECTION_REJECTIONS) + '.',
                                  'rejection_reason')
        row.status, row.rejection_reason = 'rejected', rejection_reason
    else:
        raise CorrectionError(400, 'Decyzja: publish albo reject.', 'decision')
    row.rejection_note, row.decided_at, row.decided_by = (note or '')[:600], now, staff
    row.save()
    events.log('system', row.box, meta={'correction': row.pk, 'status': row.status}, now=now)
    return row


def public_payload(row: Correction | None) -> dict | None:
    if row is None:
        return None
    return {'id': row.pk, 'box_id': row.box_id, 'text': row.text,
            'author': row.name if row.consent_public_name else legal.CORRECTION_PUBLIC_NAME_FALLBACK,
            'published_at': row.published_at.isoformat() if row.published_at else None,
            'label': 'Sprostowanie osoby, której dotyczy wpis (prawo prasowe, art. 31a)'}


def published_for(box: Box) -> Correction | None:
    """Opublikowane sprostowanie diagnozy: dla boxa diagnozy wprost, dla wpisu: jego aktualnej diagnozy."""
    target_id = box.pk
    if box.kind != 'diagnosis':
        link = BoxLink.objects.filter(box=box, kind='diagnosis_of', is_current=True).first()
        if link is None:
            return None
        target_id = link.target_id
    return Correction.objects.filter(box_id=target_id, status='published').order_by('-published_at', '-pk').first()


def status_payload(row: Correction) -> dict:
    return {'id': row.pk, 'status': row.status, 'due_at': row.due_at.isoformat(),
            'rejection_reason': row.rejection_reason or None,
            'rejection_label': legal.CORRECTION_REJECTIONS.get(row.rejection_reason) if row.rejection_reason else None}
