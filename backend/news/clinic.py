"""Klinika spinu: potok diagnoz, alerty do zatwierdzenia i dane strony /klinika.

Przepływ: nowy post z potwierdzonego konta X (obóz rządzący albo opozycja) →
selekcja → diagnoza AI → status „czeka na zatwierdzenie” → e-mail z alertem →
zatwierdzenie albo odrzucenie (bez edycji) → publikacja.
"""
from __future__ import annotations

import logging
import os
import smtplib
from datetime import datetime, time, timedelta
from email.message import EmailMessage

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from news import clinic_ai
from news.clinic_models import ClinicDailyMessage, SpinDiagnosis
from news.political_models import PoliticalAccount, PoliticalPost, PublicFigure, SocialHandleEvidence

logger = logging.getLogger(__name__)

CAMPS = ('government', 'opposition')
CAMP_LABELS = {'government': 'Rządzący', 'opposition': 'Opozycja'}
CAMP_PROMPT_LABELS = {'government': 'obóz rządzący', 'opposition': 'opozycja'}
# Kod klubu z API Sejmu → skrót na plakietce i pełna nazwa (tylko te, których nazwę znamy na pewno).
CLUBS = {
    'KO': ('KO', 'Koalicja Obywatelska'),
    'PiS': ('PiS', 'Prawo i Sprawiedliwość'),
    'PSL-TD': ('PSL', 'Polskie Stronnictwo Ludowe'),
    'Polska2050': ('PL2050', 'Polska 2050'),
    'Lewica': ('Lewica', 'Lewica'),
    'Razem': ('Razem', 'Partia Razem'),
    'Konfederacja': ('Konf.', 'Konfederacja'),
    'Konfederacja_KP': ('KKP', 'Konfederacja Korony Polskiej'),
    'niez.': ('niez.', 'posłowie niezrzeszeni'),
}
VERDICT_LABELS = {'spin': 'Spin', 'partial': 'Częściowy spin', 'no_spin': 'Bez spinu', 'unclear': 'Nie da się ocenić'}
ASSESSMENT_LABELS = {'supported': 'potwierdzone', 'contradicted': 'sprzeczne ze źródłami',
                     'misleading': 'wprowadza w błąd', 'unverified': 'nie do sprawdzenia'}
SCALE_MIN_SAMPLE = 10
NOTICE = ('Diagnozy przygotowuje AI automatycznie. Człowiek może je tylko zatwierdzić albo odrzucić — '
          'nie zmienia ich treści. Na razie diagnoza to tekst; w miarę rozbudowy bazy dowodami będą boxy '
          'z materiałami źródłowymi.')


# --- osoby i partie -------------------------------------------------------------------------

def figures_by_account(account_ids) -> dict[int, PublicFigure]:
    """Konto X → osoba z rejestru, wyłącznie przez potwierdzony dowód (nigdy po nazwie)."""
    account_ids = list(account_ids)
    if not account_ids:
        return {}
    figure_type = ContentType.objects.get_for_model(PublicFigure)
    evidence = SocialHandleEvidence.objects.filter(
        platform='x', status='candidate_created', candidate__resolved_account_id__in=account_ids,
    ).values('candidate__resolved_account_id', 'subject_content_type_id', 'subject_object_id', 'roster_entry_id')
    by_figure, by_roster = {}, {}
    for row in evidence:
        account_id = row['candidate__resolved_account_id']
        if row['subject_content_type_id'] == figure_type.id and row['subject_object_id']:
            by_figure.setdefault(account_id, row['subject_object_id'])
        elif row['roster_entry_id']:
            by_roster.setdefault(account_id, row['roster_entry_id'])
    figures = PublicFigure.objects.filter(
        Q(pk__in=by_figure.values()) | Q(parliamentary_roster_entry_id__in=by_roster.values()), archived=False,
    ).select_related('parliamentary_roster_entry')
    figure_by_id = {figure.pk: figure for figure in figures}
    figure_by_roster = {figure.parliamentary_roster_entry_id: figure for figure in figures if figure.parliamentary_roster_entry_id}
    result = {}
    for account_id in account_ids:
        figure = figure_by_id.get(by_figure.get(account_id)) or figure_by_roster.get(by_roster.get(account_id))
        if figure:
            result[account_id] = figure
    return result


def party_data(figure: PublicFigure | None):
    if figure is None:
        return None
    code = (figure.parliamentary_roster_entry.club if figure.parliamentary_roster_entry_id else '') or figure.political_alignment
    if not code:
        return None
    short, name = CLUBS.get(code, (code, code))
    return {'code': code, 'short': short, 'name': name}


def author_data(post: PoliticalPost, figure: PublicFigure | None) -> dict:
    author = post.author_data or {}
    avatar = author.get('profile_image_url') or ''
    return {
        'name': figure.canonical_name if figure else (author.get('name') or post.account.display_name),
        'handle': post.account.handle,
        'account_url': f'https://x.com/{post.account.handle}',
        'avatar_url': avatar.replace('_normal.', '_bigger.') if avatar else '',
        'figure_id': figure.pk if figure else None,
        'role_title': figure.role_title if figure else '',
        'party': party_data(figure),
    }


# --- potok diagnoz --------------------------------------------------------------------------

def _post_context(post: PoliticalPost, figure: PublicFigure | None) -> dict:
    party = party_data(figure)
    media = [item.get('type', 'załącznik') + (f" (opis: {item['alt_text']})" if item.get('alt_text') else '')
             for item in post.media or [] if isinstance(item, dict)]
    return {
        'author': figure.canonical_name if figure else post.account.display_name,
        'role': figure.role_title if figure else '',
        'club': party['name'] if party else '',
        'camp_label': CAMP_PROMPT_LABELS.get(post.camp_at_collection, post.camp_at_collection),
        'published_at': timezone.localtime(post.published_at).strftime('%Y-%m-%d %H:%M'),
        'url': post.url,
        'text': post.text,
        'media_notes': ', '.join(media),
    }


def eligible_posts():
    since = timezone.now() - timedelta(days=int(os.environ.get('CLINIC_MAX_POST_AGE_DAYS', '3')))
    return (PoliticalPost.objects.filter(available=True, camp_at_collection__in=CAMPS, published_at__gte=since,
                                         account__enabled=True, spin_diagnosis__isnull=True)
            .select_related('account').order_by('published_at', 'pk'))


def diagnoses_today() -> int:
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return SpinDiagnosis.objects.filter(created_at__gte=start, provider='anthropic').count()


def diagnose_post(post: PoliticalPost, figure: PublicFigure | None = None) -> SpinDiagnosis | None:
    context = _post_context(post, figure)
    triage = clinic_ai.triage(post.text)
    fields = {'triage': triage or {}, 'prompt_version': clinic_ai.PROMPT_VERSION}
    if triage is not None and not triage['analyze']:
        fields.update(status='not_applicable', provider='groq', model_name=triage.get('model', ''))
    else:
        try:
            result = clinic_ai.diagnose(context)
        except clinic_ai.ClinicAIError as error:
            fields.update(status='failed', error=error.code, provider='anthropic', model_name=clinic_ai.model_name())
        else:
            usage = result.pop('usage', {})
            fields.update(result, status='pending_review', provider='anthropic',
                          model_name=usage.get('model') or clinic_ai.model_name(), usage=usage)
    try:
        with transaction.atomic():
            return SpinDiagnosis.objects.create(post=post, **fields)
    except IntegrityError:
        return None  # inny proces zdiagnozował ten post w międzyczasie


def run_diagnoses(limit: int = 5) -> dict:
    if not clinic_ai.enabled():
        return {'status': 'disabled'}
    budget = int(os.environ.get('CLINIC_DAILY_LIMIT', '80')) - diagnoses_today()
    posts = list(eligible_posts()[:max(0, min(limit, budget))])
    figures = figures_by_account({post.account_id for post in posts})
    counts = {}
    for post in posts:
        diagnosis = diagnose_post(post, figures.get(post.account_id))
        if diagnosis:
            counts[diagnosis.status] = counts.get(diagnosis.status, 0) + 1
    alert = send_review_alert()
    return {'status': 'ok', 'budget_left': max(0, budget - len(posts)), 'created': counts, 'alert': alert}


def run_daily_messages(day=None) -> dict:
    if not clinic_ai.enabled():
        return {'status': 'disabled'}
    day = day or timezone.localdate()
    start = timezone.make_aware(datetime.combine(day, time.min))
    created = {}
    for camp in CAMPS:
        if ClinicDailyMessage.objects.filter(day=day, camp=camp).exclude(status='failed').exists():
            continue
        posts = list(PoliticalPost.objects.filter(
            available=True, camp_at_collection=camp, account__enabled=True,
            published_at__gte=start, published_at__lt=start + timedelta(days=1),
        ).select_related('account').order_by('-published_at')[:60])
        if len(posts) < 3:
            continue
        figures = figures_by_account({post.account_id for post in posts})
        rows = [{'author': (figures[p.account_id].canonical_name if p.account_id in figures else p.account.display_name),
                 'text': p.text[:1200]} for p in posts]
        try:
            result = clinic_ai.daily_message(CAMP_PROMPT_LABELS[camp], day.isoformat(), rows)
        except clinic_ai.ClinicAIError as error:
            logger.warning('clinic daily message failed: %s', error.code)
            continue
        ClinicDailyMessage.objects.filter(day=day, camp=camp, status='failed').delete()
        message = ClinicDailyMessage.objects.create(
            day=day, camp=camp, message=result['message'], themes=result['themes'], usage=result['usage'],
            model_name=result['usage'].get('model') or clinic_ai.model_name(), prompt_version=clinic_ai.PROMPT_VERSION)
        message.posts.set(posts)
        created[camp] = message.pk
    alert = send_review_alert()
    return {'status': 'ok', 'created': created, 'alert': alert}


# --- alerty ---------------------------------------------------------------------------------

def _smtp_ready() -> bool:
    required = ('SOURCE_MAIL_SMTP_HOST', 'SOURCE_MAIL_SMTP_USERNAME', 'SOURCE_MAIL_SMTP_PASSWORD', 'SOURCE_MAIL_SMTP_FROM')
    return bool(settings.SOURCE_MAIL_SMTP_ENABLED and all(getattr(settings, item, '') for item in required))


def send_review_alert() -> str:
    """Jeden e-mail na partię nowych diagnoz. Bez skonfigurowanego SMTP kolejka czeka w /editor/klinika."""
    diagnoses = SpinDiagnosis.objects.filter(status='pending_review', alert_sent_at__isnull=True)
    messages = ClinicDailyMessage.objects.filter(status='pending_review', alert_sent_at__isnull=True)
    count_d, count_m = diagnoses.count(), messages.count()
    if not count_d and not count_m:
        return 'nothing'
    recipient = os.environ.get('CLINIC_REVIEW_EMAIL', '').strip()
    status = 'queued_only'
    if recipient and _smtp_ready():
        domain = os.environ.get('SPIN_DOMAIN', 'spin.clinic')
        email = EmailMessage()
        email['From'] = settings.SOURCE_MAIL_SMTP_FROM
        email['To'] = recipient
        email['Subject'] = f'Klinika spinu: {count_d} diagnoz i {count_m} przekazów dnia czeka na decyzję'
        email.set_content(
            f'Nowe diagnozy do zatwierdzenia: {count_d}\nNowe przekazy dnia: {count_m}\n\n'
            f'Kolejka: https://{domain}/editor/klinika\n\n'
            'Możesz zatwierdzić albo odrzucić każdą pozycję. Treści diagnoz nie da się edytować.')
        try:
            with smtplib.SMTP_SSL(settings.SOURCE_MAIL_SMTP_HOST, settings.SOURCE_MAIL_SMTP_PORT, timeout=20) as client:
                client.login(settings.SOURCE_MAIL_SMTP_USERNAME, settings.SOURCE_MAIL_SMTP_PASSWORD)
                client.send_message(email)
            status = 'sent'
        except (OSError, smtplib.SMTPException) as error:
            logger.warning('clinic alert e-mail failed: %s', type(error).__name__)
            return 'failed'
    now = timezone.now()
    diagnoses.update(alert_sent_at=now)
    messages.update(alert_sent_at=now)
    return status


def review(obj, staff, decision: str):
    if decision not in ('approve', 'reject'):
        raise ValueError('decision')
    if obj.status != 'pending_review':
        raise ValueError('status')
    obj.status = 'approved' if decision == 'approve' else 'rejected'
    obj.reviewed_by, obj.reviewed_at = staff, timezone.now()
    obj.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
    return obj


# --- dane publiczne -------------------------------------------------------------------------

def published_diagnoses():
    return (SpinDiagnosis.objects.filter(status='approved', hidden_at__isnull=True, post__available=True)
            .select_related('post__account'))


def _media(post: PoliticalPost) -> list[dict]:
    result = []
    for item in post.media or []:
        if not isinstance(item, dict):
            continue
        url = item.get('url') or item.get('thumbnail_url') or item.get('preview_image_url')
        if url:
            result.append({'type': item.get('type', 'photo'), 'url': url, 'alt': item.get('alt_text', '')})
    return result[:4]


def card_data(diagnosis: SpinDiagnosis, figures: dict, counts: dict | None = None) -> dict:
    post = diagnosis.post
    metrics = (post.source_data or {}).get('public_metrics', {})
    return {
        'id': diagnosis.pk,
        'camp': post.camp_at_collection,
        'camp_label': CAMP_LABELS.get(post.camp_at_collection, ''),
        'verdict': diagnosis.verdict,
        'verdict_label': VERDICT_LABELS.get(diagnosis.verdict, ''),
        'intensity': diagnosis.intensity,
        'headline': diagnosis.headline,
        'summary': diagnosis.summary,
        'technique_names': [item['name'] for item in diagnosis.techniques][:4],
        'post': {'id': post.post_id, 'url': post.url, 'text': post.text, 'published_at': post.published_at,
                 'media': _media(post), 'likes': metrics.get('like_count', 0), 'reposts': metrics.get('retweet_count', 0)},
        'author': author_data(post, figures.get(post.account_id)),
        'opinions': counts or {'positive': 0, 'negative': 0},
    }


def detail_data(diagnosis: SpinDiagnosis) -> dict:
    figures = figures_by_account([diagnosis.post.account_id])
    counts = {'positive': 0, 'negative': 0}
    counts.update({row['polarity']: row['n'] for row in diagnosis.opinions.values('polarity').annotate(n=Count('id'))})
    data = card_data(diagnosis, figures, counts)
    data.update({
        'analysis': diagnosis.analysis,
        'techniques': diagnosis.techniques,
        'claims': [{**claim, 'assessment_label': ASSESSMENT_LABELS.get(claim.get('assessment'), '')} for claim in diagnosis.claims],
        'limitations': diagnosis.limitations,
        'model': diagnosis.model_name,
        'prompt_version': diagnosis.prompt_version,
        'created_at': diagnosis.created_at,
        'reviewed_at': diagnosis.reviewed_at,
        'notice': NOTICE,
    })
    return data


def _opinion_counts(ids) -> dict[int, dict]:
    from news.clinic_models import SpinOpinion
    result = {pk: {'positive': 0, 'negative': 0} for pk in ids}
    for row in SpinOpinion.objects.filter(diagnosis_id__in=ids).values('diagnosis_id', 'polarity').annotate(n=Count('id')):
        result[row['diagnosis_id']][row['polarity']] = row['n']
    return result


def cards(queryset) -> list[dict]:
    rows = list(queryset)
    figures = figures_by_account({row.post.account_id for row in rows})
    counts = _opinion_counts([row.pk for row in rows])
    return [card_data(row, figures, counts[row.pk]) for row in rows]


def scale_data(window_days: int = 7) -> dict:
    """Waga: udział postów ze spinem w zatwierdzonych diagnozach każdej strony.

    Porównujemy udział, nie liczbę — strony mają różną liczbę kont i postów.
    „Częściowy spin” liczy się za pół, „nie da się ocenić” nie wchodzi do mianownika.
    """
    since = timezone.now() - timedelta(days=window_days)
    rows = (published_diagnoses().filter(post__published_at__gte=since)
            .values('post__camp_at_collection', 'verdict').annotate(n=Count('id')))
    sides = {camp: {'spin': 0, 'partial': 0, 'no_spin': 0, 'unclear': 0} for camp in CAMPS}
    for row in rows:
        camp = row['post__camp_at_collection']
        if camp in sides and row['verdict'] in sides[camp]:
            sides[camp][row['verdict']] = row['n']
    result = {'window_days': window_days, 'min_sample': SCALE_MIN_SAMPLE}
    for camp, values in sides.items():
        assessed = values['spin'] + values['partial'] + values['no_spin']
        share = (values['spin'] + 0.5 * values['partial']) / assessed if assessed else None
        result[camp] = {**values, 'assessed': assessed, 'share': round(share, 4) if share is not None else None}
    result['enough_data'] = all(result[camp]['assessed'] >= SCALE_MIN_SAMPLE for camp in CAMPS)
    return result


def daily_message_data(camp: str):
    message = ClinicDailyMessage.objects.filter(camp=camp, status='approved').order_by('-day').first()
    if not message:
        return None
    return {'day': message.day, 'message': message.message, 'themes': message.themes,
            'posts_count': message.posts.count(), 'model': message.model_name}


def spin_of_day():
    base = published_diagnoses().filter(verdict__in=['spin', 'partial'])
    now = timezone.now()
    for hours in (24, 72):
        best = base.filter(post__published_at__gte=now - timedelta(hours=hours)).order_by('-intensity', '-post__published_at').first()
        if best:
            return detail_data(best)
    return None


def clinic_page_data(window_days: int = 7, per_camp: int = 12) -> dict:
    columns = {camp: cards(published_diagnoses().filter(post__camp_at_collection=camp)
                           .order_by('-post__published_at', '-pk')[:per_camp]) for camp in CAMPS}
    return {
        'notice': NOTICE,
        'scale': scale_data(window_days),
        'messages': {camp: daily_message_data(camp) for camp in CAMPS},
        'spin_of_day': spin_of_day(),
        'columns': columns,
        'accounts_count': reading_accounts().count(),
    }


def reading_accounts():
    return PoliticalAccount.objects.filter(enabled=True, camp__in=CAMPS)


def accounts_data() -> list[dict]:
    accounts = [account for account in reading_accounts().select_related('confirmed_by').order_by('camp', 'display_name')
                if account.is_confirmed()]
    figures = figures_by_account([account.pk for account in accounts])
    posts = dict(PoliticalPost.objects.filter(account__in=accounts, available=True).values_list('account_id').annotate(n=Count('id')))
    return [{
        'handle': account.handle,
        'url': f'https://x.com/{account.handle}',
        'display_name': account.display_name,
        'camp': account.camp,
        'camp_label': CAMP_LABELS[account.camp],
        'figure_id': figures[account.pk].pk if account.pk in figures else None,
        'figure_name': figures[account.pk].canonical_name if account.pk in figures else '',
        'party': party_data(figures.get(account.pk)),
        'posts_collected': posts.get(account.pk, 0),
        'last_polled_at': account.last_polled_at,
    } for account in accounts]
