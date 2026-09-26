"""Klinika spinu: potok diagnoz, alerty do zatwierdzenia i dane strony /klinika.

Przepływ: nowy post z potwierdzonego konta X (obóz rządzący albo opozycja) → strażnik (darmowe
modele, ocena 0–100) → wysoka ocena: kolejka płatnej diagnozy; średnia: oznaczenie i decyzja
„Zbadaj”; niska: pominięcie → diagnoza AI → „czeka na zatwierdzenie” → e-mail z alertem →
zatwierdzenie albo odrzucenie (bez edycji) → publikacja.
"""
from __future__ import annotations

import logging
import math
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
NOTICE_AUTO = ('Strażnik (darmowe modele) wybiera posty warte sprawdzenia, Claude stawia diagnozę ze źródłami, '
               'a publikacja jest automatyczna — nikt nie poprawia treści diagnoz.')
NOTICE_REVIEW = ('Diagnozy przygotowuje AI. Człowiek może je tylko zatwierdzić albo odrzucić — nie zmienia ich treści.')
NOTICE = NOTICE_AUTO


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


def unscreened_posts():
    since = timezone.now() - timedelta(days=int(os.environ.get('CLINIC_MAX_POST_AGE_DAYS', '3')))
    return (PoliticalPost.objects.filter(available=True, camp_at_collection__in=CAMPS, published_at__gte=since,
                                         account__enabled=True, spin_diagnosis__isnull=True)
            .select_related('account').order_by('published_at', 'pk'))


def auto_publish() -> bool:
    """Tryb w pełni automatyczny (domyślny): diagnoza publikuje się sama, oznaczona jako wygenerowana przez AI."""
    return os.environ.get('CLINIC_AUTO_PUBLISH', 'true').lower() == 'true'


def thresholds() -> tuple[int, int]:
    """(próg oznaczenia, próg automatycznej diagnozy). Poniżej pierwszego — pomijamy za darmo."""
    flag = int(os.environ.get('CLINIC_FLAG_THRESHOLD', '40'))
    auto = int(os.environ.get('CLINIC_AUTO_THRESHOLD', '75'))
    return flag, max(flag, auto)


def local_now():
    """Czas lokalny — osobna funkcja, żeby testy mogły ustawić porę dnia."""
    return timezone.localtime()


def diagnoses_today() -> int:
    """Udane diagnozy od północy — tylko one zużywają dzienny limit."""
    return _anthropic_today().exclude(status='failed').count()


def featured_today():
    """Dzisiejsza diagnoza z zarezerwowanego miejsca na najpopularniejszy post (kandydat na spin dnia)."""
    return _anthropic_today().exclude(status='failed').filter(triage__featured_day=local_now().date().isoformat()).first()


def failures_today() -> int:
    return _anthropic_today().filter(status='failed').count()


def _anthropic_today():
    start = local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    return SpinDiagnosis.objects.filter(diagnosed_at__gte=start, provider='anthropic')


def screen_post(post: PoliticalPost) -> SpinDiagnosis | None:
    """Strażnik — darmowa ocena. Tworzy wpis: pominięty, oznaczony do decyzji albo w kolejce do diagnozy."""
    result = clinic_ai.screen(post.text)
    flag, auto = thresholds()
    if result is None:
        # Żaden darmowy model nie odpowiedział: nie płacimy w ciemno — post czeka na decyzję człowieka.
        fields = {'status': 'flagged', 'triage': {'reason': 'Strażnik niedostępny — oceń ręcznie.'}}
    else:
        score = result['score']
        status = 'queued' if score >= auto else 'flagged' if score >= flag else 'not_applicable'
        fields = {'status': status, 'triage': result, 'screen_score': score,
                  'provider': result['provider'], 'model_name': result['model']}
    try:
        with transaction.atomic():
            return SpinDiagnosis.objects.create(post=post, prompt_version=clinic_ai.PROMPT_VERSION, **fields)
    except IntegrityError:
        return None


def run_screening(limit: int = 30) -> dict:
    counts = {}
    for post in unscreened_posts()[:limit]:
        row = screen_post(post)
        if row:
            counts[row.status] = counts.get(row.status, 0) + 1
    alert = send_review_alert() if counts.get('flagged') else 'nothing'
    return {'screened': counts, 'alert': alert}


def diagnose(row: SpinDiagnosis, figure: PublicFigure | None = None) -> SpinDiagnosis:
    """Płatna diagnoza (Claude) jednego wpisu z kolejki."""
    try:
        result = clinic_ai.diagnose(_post_context(row.post, figure))
    except clinic_ai.ClinicAIError as error:
        row.status, row.error = 'failed', error.code
        row.provider, row.model_name = 'anthropic', clinic_ai.model_name()
    else:
        usage = result.pop('usage', {})
        for field, value in result.items():
            setattr(row, field, value)
        row.status, row.usage, row.error = ('approved' if auto_publish() else 'pending_review'), usage, ''
        if row.status == 'approved':
            row.reviewed_at = timezone.now()
        row.provider, row.model_name = 'anthropic', usage.get('model') or clinic_ai.model_name()
    row.diagnosed_at = timezone.now()
    row.prompt_version = clinic_ai.PROMPT_VERSION
    row.save()
    return row


def queue_for_diagnosis(row: SpinDiagnosis) -> SpinDiagnosis:
    """Decyzja człowieka „Zbadaj” dla wpisu oznaczonego przez strażnika. Nie zmienia żadnej treści."""
    if row.status not in ('flagged', 'not_applicable', 'failed'):
        raise ValueError('status')
    row.status = 'queued'
    row.save(update_fields=['status'])
    return row


def dismiss_flag(row: SpinDiagnosis) -> SpinDiagnosis:
    """Decyzja „Pomiń” — post nie zostanie zbadany (i nic nie kosztuje)."""
    if row.status != 'flagged':
        raise ValueError('status')
    row.status = 'not_applicable'
    row.save(update_fields=['status'])
    return row


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def day_window(now):
    """Godziny, w których publikujemy diagnozy (domyślnie 7:00–23:00). W nocy Klinika śpi."""
    start = now.replace(hour=_env_int('CLINIC_DAY_START_HOUR', 7), minute=0, second=0, microsecond=0)
    end = now.replace(hour=min(23, _env_int('CLINIC_DAY_END_HOUR', 23)), minute=0, second=0, microsecond=0)
    return start, end


def paced_target(now, regular_limit: int) -> int:
    """Ile zwykłych diagnoz powinno już być o tej porze — limit rozłożony równo na dzień, nie w pierwszej godzinie."""
    start, end = day_window(now)
    if now < start or end <= start:
        return 0
    if now >= end:
        return regular_limit
    return min(regular_limit, math.ceil(regular_limit * (now - start) / (end - start)))


def _post_popularity(post, followers: dict[int, int]) -> int:
    """Zasięg posta: obserwujący autora i reakcje zapisane przy pobraniu (polubienia, podania dalej, odpowiedzi, cytaty)."""
    metrics = (post.source_data or {}).get('public_metrics') or {}
    engagement = (metrics.get('like_count', 0) + 2 * metrics.get('retweet_count', 0)
                  + metrics.get('reply_count', 0) + 2 * metrics.get('quote_count', 0))
    return followers.get(post.account_id, 0) + 50 * engagement


def _followers_by_account(account_ids) -> dict[int, int]:
    followers = {}
    for account_id, author in (PoliticalPost.objects.filter(account_id__in=account_ids).exclude(author_data={})
                               .order_by('account_id', '-published_at').values_list('account_id', 'author_data')):
        if account_id not in followers:
            count = ((author or {}).get('public_metrics') or {}).get('followers_count')
            if isinstance(count, int):
                followers[account_id] = count
    return followers


def pick_featured():
    """Najpopularniejszy dzisiejszy post, który strażnik uznał za wart sprawdzenia — zarezerwowane miejsce na spin dnia."""
    flag, _ = thresholds()
    since = local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    candidates = list(SpinDiagnosis.objects.filter(status__in=['queued', 'flagged'], screen_score__gte=flag,
                                                   post__published_at__gte=since)
                      .select_related('post__account')[:500])
    if not candidates:
        return None
    followers = _followers_by_account({row.post.account_id for row in candidates})
    best = max(candidates, key=lambda row: (_post_popularity(row.post, followers), row.screen_score or 0))
    best.triage = {**(best.triage or {}), 'featured_day': local_now().date().isoformat(),
                   'popularity': _post_popularity(best.post, followers)}
    best.save(update_fields=['triage'])
    return best


def run_diagnoses(limit: int = 2) -> dict:
    """Płatne diagnozy rozłożone na dzień: zwykłe równo od rana do wieczora, a jedno miejsce czeka na
    najpopularniejszy post dnia (od CLINIC_FEATURED_HOUR) — to on zostaje spinem dnia."""
    if not clinic_ai.enabled():
        return {'status': 'disabled'}
    if failures_today() >= _env_int('CLINIC_DAILY_FAILURE_LIMIT', 5):
        # Seria błędów (klucz, model, limit konta) — nie palimy pieniędzy do jutra albo do naprawy.
        return {'status': 'too_many_failures', 'failed_today': failures_today()}
    now = local_now()
    start, end = day_window(now)
    if not start <= now < end:
        return {'status': 'night'}
    daily = _env_int('CLINIC_DAILY_LIMIT', 20)
    reserve = 1 if daily > 1 else 0
    counts = {}
    featured = featured_today()
    if reserve and not featured and now.hour >= _env_int('CLINIC_FEATURED_HOUR', 18) and diagnoses_today() < daily:
        row = pick_featured()
        if row:
            figure = figures_by_account({row.post.account_id}).get(row.post.account_id)
            diagnose(row, figure)
            counts[f'featured_{row.status}'] = 1
    regular_done = diagnoses_today() - (1 if featured_today() else 0)
    take = max(0, min(limit, paced_target(now, daily - reserve) - regular_done))
    rows = list(SpinDiagnosis.objects.filter(status='queued').select_related('post__account')
                .order_by('-screen_score', 'post__published_at')[:take])
    if auto_publish() and len(rows) < take:
        # Żeby spiny wpadały codziennie: gdy wysoko ocenionych postów brakuje, bierzemy najwyżej ocenione
        # z oznaczonych przez strażnika (z ostatniej doby), aż do dziennego limitu.
        since = timezone.now() - timedelta(hours=36)
        extra = (SpinDiagnosis.objects.filter(status='flagged', screen_score__isnull=False, post__published_at__gte=since)
                 .select_related('post__account').order_by('-screen_score', '-post__published_at')[:take - len(rows)])
        rows += list(extra)
    figures = figures_by_account({row.post.account_id for row in rows})
    for row in rows:
        diagnose(row, figures.get(row.post.account_id))
        counts[row.status] = counts.get(row.status, 0) + 1
    alert = send_review_alert()
    return {'status': 'ok', 'budget_left': max(0, daily - diagnoses_today()), 'diagnosed': counts, 'alert': alert}


MIN_MESSAGE_ACCOUNTS = 3


def run_daily_messages(day=None) -> dict:
    """Przekaz dnia każdego obozu — darmowe modele (Groq, zapasowo NIM), z postów co najmniej trzech kont.

    W ciągu dnia przekaz jest odświeżany (9:00, 12:00, 15:00, 18:00, 21:30), dopóki nikt go ręcznie nie zatwierdził.
    """
    day = day or timezone.localdate()
    start = timezone.make_aware(datetime.combine(day, time.min))
    created = {}
    for camp in CAMPS:
        existing = ClinicDailyMessage.objects.filter(day=day, camp=camp).first()
        if existing and existing.reviewed_by_id:
            continue  # zatwierdzony ręcznie — nie nadpisujemy
        posts = list(PoliticalPost.objects.filter(
            available=True, camp_at_collection=camp, account__enabled=True,
            published_at__gte=start, published_at__lt=start + timedelta(days=1),
        ).select_related('account').order_by('-published_at')[:60])
        if len({post.account_id for post in posts}) < MIN_MESSAGE_ACCOUNTS:
            continue
        figures = figures_by_account({post.account_id for post in posts})
        rows = [{'author': (figures[p.account_id].canonical_name if p.account_id in figures else p.account.display_name),
                 'text': p.text[:1200]} for p in posts]
        try:
            result = clinic_ai.daily_message(CAMP_PROMPT_LABELS[camp], day.isoformat(), rows)
        except clinic_ai.ClinicAIError as error:
            logger.warning('clinic daily message failed: %s', error.code)
            continue
        status = 'approved' if auto_publish() else 'pending_review'
        message, _ = ClinicDailyMessage.objects.update_or_create(day=day, camp=camp, defaults={
            'message': result['message'], 'themes': result['themes'], 'usage': result['usage'], 'status': status,
            'model_name': result['usage'].get('model', ''), 'prompt_version': clinic_ai.PROMPT_VERSION,
            'reviewed_at': timezone.now() if status == 'approved' else None})
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
    diagnoses = SpinDiagnosis.objects.filter(status__in=['pending_review', 'flagged'], alert_sent_at__isnull=True)
    messages = ClinicDailyMessage.objects.filter(status='pending_review', alert_sent_at__isnull=True)
    count_d = diagnoses.filter(status='pending_review').count()
    count_f = diagnoses.filter(status='flagged').count()
    count_m = messages.count()
    if not count_d and not count_m and not count_f:
        return 'nothing'
    recipient = os.environ.get('CLINIC_REVIEW_EMAIL', '').strip()
    status = 'queued_only'
    if recipient and _smtp_ready():
        domain = os.environ.get('SPIN_DOMAIN', 'spin.clinic')
        email = EmailMessage()
        email['From'] = settings.SOURCE_MAIL_SMTP_FROM
        email['To'] = recipient
        email['Subject'] = f'Klinika spinu: {count_d} diagnoz, {count_f} postów wartych zbadania, {count_m} przekazów dnia'
        email.set_content(
            f'Nowe diagnozy do zatwierdzenia: {count_d}\n'
            f'Posty oznaczone przez strażnika (decyzja „Zbadaj” uruchamia płatną diagnozę): {count_f}\n'
            f'Nowe przekazy dnia: {count_m}\n\n'
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
        'auto_published': diagnosis.status == 'approved' and not diagnosis.reviewed_by_id,
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
    """Najpierw diagnoza najpopularniejszego posta dnia (zarezerwowane miejsce), o ile wykazała spin;
    inaczej — najsilniejszy spin z ostatniej doby."""
    base = published_diagnoses().filter(verdict__in=['spin', 'partial'])
    now = timezone.now()
    featured = base.filter(triage__has_key='featured_day', diagnosed_at__gte=now - timedelta(hours=26)).order_by('-diagnosed_at').first()
    if featured:
        return detail_data(featured)
    for hours in (24, 72):
        best = base.filter(post__published_at__gte=now - timedelta(hours=hours)).order_by('-intensity', '-post__published_at').first()
        if best:
            return detail_data(best)
    return None


def clinic_page_data(window_days: int = 7, per_camp: int = 20) -> dict:
    columns = {camp: cards(published_diagnoses().filter(post__camp_at_collection=camp)
                           .order_by('-post__published_at', '-pk')[:per_camp]) for camp in CAMPS}
    return {
        'notice': NOTICE_AUTO if auto_publish() else NOTICE_REVIEW,
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
