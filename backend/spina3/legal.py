"""Wymagania prawne S2 (audyt 14.10.2026): podstawy decyzji, uzasadnienia (DSA art. 17), odwołania, sprostowania,
cisza wyborcza kont, zgoda art. 9 RODO z oświadczeniem wieku.

Zasady: dane osobowe tylko tam, gdzie wymaga ich prawo; każde ograniczenie treści albo konta ma zapisane uzasadnienie;
żaden publiczny endpoint nie ujawnia ocen jednostkowych. Stałe są nazwane, nie numerowane: treść podstaw uzupełnia się
po przeglądzie Regulaminu (decyzja właściciela 14.10), bez zmiany kluczy zapisanych w bazie.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

# --- podstawy decyzji (Regulamin spina3.pl i przepisy) -----------------------------------------------------------
# Teksty do uzupełnienia po przeglądzie Regulaminu przez radcę; klucze są trwałe (zapisywane w ModerationDecision.basis).
REGULAMIN_SEKCJA_TRESCI_NIEZGODNE = 'regulamin_tresci_niezgodne'
REGULAMIN_SEKCJA_DANE_OSOBOWE = 'regulamin_dane_osobowe'
REGULAMIN_SEKCJA_GROZBY = 'regulamin_grozby_obrazy'
REGULAMIN_SEKCJA_SPAM = 'regulamin_spam'
REGULAMIN_SEKCJA_PRAWA_AUTORSKIE = 'regulamin_prawa_autorskie'
REGULAMIN_SEKCJA_ZRODLA = 'regulamin_zrodla_niedozwolone'
REGULAMIN_SEKCJA_KONTO = 'regulamin_zasady_konta'
PRZEPIS_TRESC_NIELEGALNA = 'przepis_tresc_nielegalna'
PRZEPIS_RODO_ART_17 = 'przepis_rodo_art17'

BASES = {
    REGULAMIN_SEKCJA_TRESCI_NIEZGODNE: 'Regulamin spina3.pl, sekcja o treściach niezgodnych z zasadami serwisu [do uzupełnienia po przeglądzie Regulaminu].',
    REGULAMIN_SEKCJA_DANE_OSOBOWE: 'Regulamin spina3.pl, sekcja o danych osób prywatnych [do uzupełnienia po przeglądzie Regulaminu].',
    REGULAMIN_SEKCJA_GROZBY: 'Regulamin spina3.pl, sekcja o groźbach i obraźliwych treściach [do uzupełnienia po przeglądzie Regulaminu].',
    REGULAMIN_SEKCJA_SPAM: 'Regulamin spina3.pl, sekcja o spamie i nadużyciach [do uzupełnienia po przeglądzie Regulaminu].',
    REGULAMIN_SEKCJA_PRAWA_AUTORSKIE: 'Regulamin spina3.pl, sekcja o prawach autorskich [do uzupełnienia po przeglądzie Regulaminu].',
    REGULAMIN_SEKCJA_ZRODLA: 'Regulamin spina3.pl, sekcja o dozwolonych źródłach i dowodach [do uzupełnienia po przeglądzie Regulaminu].',
    REGULAMIN_SEKCJA_KONTO: 'Regulamin spina3.pl, sekcja o zasadach korzystania z konta [do uzupełnienia po przeglądzie Regulaminu].',
    PRZEPIS_TRESC_NIELEGALNA: 'Treść nielegalna w rozumieniu art. 3 lit. h rozporządzenia (UE) 2022/2065 (DSA) [przepis szczególny do wskazania w decyzji].',
    PRZEPIS_RODO_ART_17: 'Art. 17 rozporządzenia (UE) 2016/679 (RODO): żądanie usunięcia danych.',
}
# Kategoria zgłoszenia -> domyślna podstawa (zespół może wskazać inną).
REPORT_BASIS = {
    'private_data': REGULAMIN_SEKCJA_DANE_OSOBOWE, 'threat': REGULAMIN_SEKCJA_GROZBY, 'illegal': PRZEPIS_TRESC_NIELEGALNA,
    'copyright': REGULAMIN_SEKCJA_PRAWA_AUTORSKIE, 'spam': REGULAMIN_SEKCJA_SPAM, 'subject': REGULAMIN_SEKCJA_DANE_OSOBOWE,
    'other': REGULAMIN_SEKCJA_TRESCI_NIEZGODNE,
}
APPEAL_MONTHS = 6
APPEAL_ROUTE = ('Odwołanie: POST me/decisions/{id}/appeal/ (na stronie decyzji: {url}) w ciągu 6 miesięcy od decyzji. '
                'Odwołanie rozpatruje człowiek z zespołu spina3. Przysługuje też pozasądowe rozstrzyganie sporów (DSA art. 21) '
                'i droga sądowa.')
RESTRICTION_LABELS = {'hide': 'ukrycie', 'remove': 'usunięcie', 'demote': 'obniżenie wagi ocen do 0', 'suspend': 'zawieszenie konta'}
TARGET_LABELS = {'pin': 'przypięcie', 'box': 'box', 'comment': 'komentarz', 'account': 'konto'}

# --- e-mail decyzji (właściciel 14.10: spina3.pl nie ma poczty) ----------------------------------------------------
DECISION_FROM_EMAIL_DEFAULT = 'spina3 <kontakt@iapply.pl>'
DECISIONS_PATH_DEFAULT = '/konto/decyzje'

# --- sprostowanie (prawo prasowe) -------------------------------------------------------------------------------
CORRECTION_DAYS = 21
CORRECTION_WORKING_DAYS = 3
CORRECTION_MAX_RATIO = 2
CORRECTION_PUBLIC_NAME_FALLBACK = 'Osoba, której dotyczy wpis'
# Odmowa wyłącznie z przyczyn z art. 33 ustawy Prawo prasowe (oznaczenia ustępów do potwierdzenia przez radcę).
CORRECTION_REJECTIONS = {
    'requirements': 'art. 33 ust. 1 pkt 1: sprostowanie nie spełnia wymogów art. 31a',
    'unlawful': 'art. 33 ust. 1 pkt 2: treść stanowiłaby przestępstwo lub naruszałaby dobra osobiste osób trzecich',
    'already_corrected': 'art. 33 ust. 2: dotyczy wypowiedzi już sprostowanej',
    'late': 'art. 33 ust. 2: nadesłane po terminie 21 dni',
}

# --- konto ------------------------------------------------------------------------------------------------------
DELETED_NICK = 'Użytkownik usunięty'
ACCOUNT_DELETION_DAYS = 30
DECISION_RETENTION_DAYS = 365   # zgłoszenia i decyzje: 12 miesięcy
EVENT_RETENTION_DAYS_DEFAULT = 90


def basis_text(key: str) -> str:
    return BASES.get(key, BASES[REGULAMIN_SEKCJA_TRESCI_NIEZGODNE])


def add_months(value: datetime, months: int) -> datetime:
    month = value.month - 1 + months
    year, month = value.year + month // 12, month % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


# --- dni robocze ------------------------------------------------------------------------------------------------

def _easter(year: int) -> date:
    """Wielkanoc (algorytm Meeusa/Jonesa/Butchera, kalendarz gregoriański)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def holidays(year: int) -> set[date]:
    """Dni ustawowo wolne od pracy w Polsce (ustawa z 18.01.1951), w tym Wigilia od 2025 r."""
    easter = _easter(year)
    days = {date(year, 1, 1), date(year, 1, 6), easter, easter + timedelta(days=1), date(year, 5, 1), date(year, 5, 3),
            easter + timedelta(days=49), easter + timedelta(days=60), date(year, 8, 15), date(year, 11, 1), date(year, 11, 11),
            date(year, 12, 25), date(year, 12, 26)}
    if year >= 2025:
        days.add(date(year, 12, 24))
    return days


def is_working_day(day: date) -> bool:
    return day.weekday() < 5 and day not in holidays(day.year)


def add_working_days(start: datetime, count: int) -> datetime:
    """Koniec `count`-tego dnia roboczego po dniu `start` (czas lokalny, 23:59:59)."""
    local = timezone.localtime(start)
    day, left = local.date(), count
    while left > 0:
        day += timedelta(days=1)
        if is_working_day(day):
            left -= 1
    return timezone.make_aware(datetime.combine(day, time(23, 59, 59)), timezone.get_current_timezone())


# --- decyzje (DSA art. 17) -----------------------------------------------------------------------------------------

def decisions_url(decision_id: int | None = None) -> str:
    base = getattr(settings, 'SPINA3_PUBLIC_URL', 'https://spina3.pl').rstrip('/')
    path = getattr(settings, 'SPINA3_DECISIONS_PATH', DECISIONS_PATH_DEFAULT)
    url = base + path
    return f'{url}#{decision_id}' if decision_id else url


def record_decision(*, user, target_type: str, restriction: str, facts: str, basis: str = '', staff=None, pin=None, box=None,
                    comment=None, report=None, automated: bool = False, until=None, now=None):
    """Zapisuje uzasadnienie i wysyła je autorowi e-mailem. Bez autora (treść systemowa, konto usunięte) nic nie zapisuje."""
    from .models import ModerationDecision
    if user is None:
        return None
    now = now or timezone.now()
    basis = basis if basis in BASES else REGULAMIN_SEKCJA_TRESCI_NIEZGODNE
    row = ModerationDecision.objects.create(
        user=user, target_type=target_type, restriction=restriction, facts=(facts or '').strip() or 'Brak opisu faktów.',
        basis=basis, basis_text=basis_text(basis), automated=automated, until=until, decided_by=staff, pin=pin, box=box,
        comment=comment, report=report, appeal_deadline=add_months(now, APPEAL_MONTHS), created_at=now)
    row.appeal_route = APPEAL_ROUTE.format(id=row.pk, url=decisions_url(row.pk))
    row.save(update_fields=['appeal_route'])
    send_decision_email(row, now)
    return row


def send_decision_email(row, now=None) -> bool:
    email = getattr(row.user, 'email', '') if row.user_id else ''
    if not email:
        return False
    context = decision_payload(row)
    context['url'] = decisions_url(row.pk)
    body = render_to_string('spina3/email/decision.txt', context)
    subject = f'spina3.pl: decyzja nr {row.pk} ({RESTRICTION_LABELS[row.restriction]})'
    sender = getattr(settings, 'SPINA3_DECISION_FROM_EMAIL', DECISION_FROM_EMAIL_DEFAULT)
    try:
        sent = send_mail(subject, body, sender, [email], fail_silently=False)
    except Exception:  # noqa: BLE001 - awaria poczty nie cofa decyzji; zostaje email_sent_at=None do ponowienia
        return False
    if sent:
        row.email_sent_at = now or timezone.now()
        row.save(update_fields=['email_sent_at'])
    return bool(sent)


def decision_payload(row) -> dict:
    """Treść decyzji dla autora (tylko właściciel): bez danych zgłaszającego i bez nazwiska moderatora."""
    appeal = getattr(row, 'appeal', None) if row.pk else None
    now = timezone.now()
    target_id = {'pin': row.pin_id, 'box': row.box_id, 'comment': row.comment_id, 'account': None}[row.target_type]
    return {
        'id': row.pk, 'target_type': row.target_type, 'target_label': TARGET_LABELS[row.target_type], 'target_id': target_id,
        'box_id': row.box_id or (row.pin.box_id if row.pin_id else (row.comment.box_id if row.comment_id else None)),
        'restriction': row.restriction, 'restriction_label': RESTRICTION_LABELS[row.restriction],
        'facts': row.facts, 'basis': row.basis, 'basis_text': row.basis_text, 'automated': row.automated,
        'decided_by': 'system (automat)' if row.automated and row.decided_by_id is None else 'zespół spina3',
        'until': row.until.isoformat() if row.until else None,
        'created_at': row.created_at.isoformat(), 'revoked_at': row.revoked_at.isoformat() if row.revoked_at else None,
        'appeal_route': row.appeal_route, 'appeal_deadline': row.appeal_deadline.isoformat(),
        'appeal': ({'id': appeal.pk, 'status': appeal.status, 'created_at': appeal.created_at.isoformat(),
                    'decision_reason': appeal.decision_reason} if appeal else None),
        'can_appeal': appeal is None and row.revoked_at is None and now <= row.appeal_deadline,
    }


def latest_open_decision(*, pin=None, comment=None):
    from .models import ModerationDecision
    qs = ModerationDecision.objects.filter(revoked_at__isnull=True, appeal__isnull=True)
    qs = qs.filter(pin=pin, target_type='pin') if pin is not None else qs.filter(comment=comment, target_type='comment')
    return qs.order_by('-created_at', '-pk').first()


def revoke_decisions(*, pin=None, box=None, comment=None, now=None) -> int:
    from .models import ModerationDecision
    filt = {'pin': pin, 'target_type': 'pin'} if pin is not None else (
        {'comment': comment, 'target_type': 'comment'} if comment is not None else {'box': box, 'target_type': 'box'})
    return ModerationDecision.objects.filter(revoked_at__isnull=True, **filt).update(revoked_at=now or timezone.now())


# --- cisza wyborcza kont kandydatów i komitetów ---------------------------------------------------------------------

def normalize_handle(value: str) -> str:
    return (value or '').strip().lstrip('@').lower()


def silenced_handles(now=None) -> set[str]:
    from .models import SilencedAccount
    now = now or timezone.now()
    return set(SilencedAccount.objects.filter(starts_at__lte=now, ends_at__gt=now).values_list('handle', flat=True))


def box_handles(box) -> set[str]:
    """Uchwyty kont, których dotyczy box: autor wpisu; dla diagnozy także autor wpisu, do którego jest przypięta."""
    handles = {normalize_handle(box.author_handle)} if box.author_handle else set()
    if box.kind == 'diagnosis':
        from .models import BoxLink
        for handle in BoxLink.objects.filter(target=box, kind='diagnosis_of').values_list('box__author_handle', flat=True):
            if handle:
                handles.add(normalize_handle(handle))
    return handles


def is_silenced(box, now=None, handles: set[str] | None = None) -> bool:
    if box is None:
        return False
    active = handles if handles is not None else silenced_handles(now)
    return bool(active and box_handles(box) & active)


def check_silence(*boxes, now=None) -> None:
    from .pins import PinError
    active = silenced_handles(now)
    if active and any(is_silenced(box, handles=active) for box in boxes if box is not None):
        raise PinError(423, 'Cisza wyborcza: przy materiałach kandydatów i komitetów nowe oceny, komentarze i przypięcia '
                            'przyjmujemy po jej zakończeniu.', 'election_silence')


# --- zgoda art. 9 RODO i wiek ---------------------------------------------------------------------------------------

def check_publish_consent(profile, trust) -> None:
    """Nowa publikacja: zgoda art. 9 i oświadczenie 16+ (profile ze zgodą sprzed S2: 403 age dopiero przy publikacji)."""
    from .pins import PinError
    if trust.is_team:
        return
    if profile.deletion_requested_at is not None:
        raise PinError(403, 'Konto spina3 jest oznaczone do usunięcia.', 'deleted')
    if profile.consent_art9_at is None:
        raise PinError(403, 'Przed pierwszą publikacją potrzebna jest zgoda na publikację stanowisk przy nicku.', 'consent')
    if profile.age_16_plus_at is None:
        raise PinError(403, 'Publikować mogą osoby, które ukończyły 16 lat: potwierdź to w zgodzie.', 'age')


@transaction.atomic
def withdraw_consent(user, now=None) -> dict:
    """Wycofanie zgody art. 9: oceny tracą wagę i autora (agregat zostaje, spinka przeliczona); komentarze odpięte od nicku
    i oznaczone do przeglądu, treść zostaje (decyzja prawna otwarta)."""
    from .models import Box, Comment, Rating, Spina3Profile
    from .spinka import recompute
    now = now or timezone.now()
    boxes: set[int] = set()
    ratings = 0
    for rating in Rating.objects.select_for_update().filter(user=user):
        rating.user, rating.account_weight, rating.anonymized = None, 0.0, True
        rating.save(update_fields=['user', 'account_weight', 'anonymized', 'updated_at'])
        boxes.add(rating.box_id)
        ratings += 1
    comments = Comment.objects.filter(user=user).update(user=None, anonymized=True, needs_review=True, updated_at=now)
    profile = Spina3Profile.for_user(user)
    profile.consent_art9_at, profile.age_16_plus_at = None, None
    profile.save(update_fields=['consent_art9_at', 'age_16_plus_at'])
    for box in Box.objects.filter(pk__in=boxes):
        recompute(box, now)
    return {'ratings_detached': ratings, 'comments_detached': comments}
