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
import unicodedata
from datetime import datetime, time, timedelta
from email.message import EmailMessage

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Count, Min, Max, Q
from django.utils import timezone

from news import clinic_ai
from news.names import display_name
from news.clinic_models import ClinicDailyMessage, SpinDiagnosis
from news.political_models import PoliticalAccount, PoliticalPost, PublicFigure, SocialHandleEvidence
from news.techniques import technique_groups, normalized
from news.clinic_scan import scan_data, synthesis_fingerprint, model_label

logger = logging.getLogger(__name__)

from news.clinic_council import check_failed, clean_claim  # noqa: E402

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
                     'misleading': 'wprowadza w błąd', 'unverified': 'niezweryfikowane'}  # jedno słowo w całym serwisie (audyt 046)
SCALE_MIN_SAMPLE = 10
NOTICE_AUTO = ('Wpisy do analizy wybiera automat. Kilka niezależnych modeli AI ocenia każdy osobno, a fakty sprawdzamy '
               'w wyszukiwarce. Przy sporze modeli albo bardzo silnym spinie fakty sprawdza dodatkowo mocniejszy model. '
               'Publikacja jest automatyczna · nikt nie poprawia treści diagnoz.')
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
    ).select_related('parliamentary_roster_entry').prefetch_related('public_roles')
    figure_by_id = {figure.pk: figure for figure in figures}
    figure_by_roster = {figure.parliamentary_roster_entry_id: figure for figure in figures if figure.parliamentary_roster_entry_id}
    result = {}
    for account_id in account_ids:
        figure = figure_by_id.get(by_figure.get(account_id)) or figure_by_roster.get(by_roster.get(account_id))
        if figure:
            result[account_id] = figure
    return result


EU_GROUPS = {'pfe', 'ppe', 'epp', 'ecr', 's d', 'renew', 'renew europe', 'greens efa',
             'zieloni wse', 'the left', 'gue ngl', 'esn', 'ni', 'id', 'patriots for europe'}


def clean_account_name(value):
    """Usuwa symbole emoji, selektory wariantów i łączniki sekwencji emoji."""
    return ' '.join(''.join(char for char in (value or '')
                           if unicodedata.category(char) not in {'So', 'Sk', 'Cf'}
                           and not ('\ufe00' <= char <= '\ufe0f')
                           and char != '\u20e3').split())


def party_affiliation(figure):
    """Zwraca krajową afiliację i osobno frakcję PE; nie zgaduje po nazwisku."""
    if figure is None:
        return {'party': None, 'eu_group': None, 'source': None}
    today = local_now().date()
    roles = sorted((role for role in figure.public_roles.all()
                    if not role.archived and role.status == 'current'
                    and (role.since is None or role.since <= today)
                    and (role.until is None or role.until >= today)),
                   key=lambda role: (role.source_checked_at, role.pk), reverse=True)
    candidates = [(role.party, 'role.party') for role in roles]
    candidates += [(figure.parliamentary_roster_entry.club, 'roster.club')] if figure.parliamentary_roster_entry_id else []
    candidates += [(figure.political_alignment, 'figure.political_alignment')]
    result = {'party': None, 'eu_group': None, 'source': None}
    for value, source in candidates:
        code = clean_account_name(value)
        if not code:
            continue
        if normalized(code) in EU_GROUPS:
            result['eu_group'] = result['eu_group'] or code
        elif result['party'] is None:
            code = next((key for key, labels in CLUBS.items()
                         if normalized(code) in {normalized(key), *(normalized(label) for label in labels)}), code)
            short, name = CLUBS.get(code, (code, code))
            result.update(party={'code': code, 'short': short, 'name': name}, source=source)
    return result


def party_data(figure: PublicFigure | None):
    return party_affiliation(figure)['party']


def author_data(post: PoliticalPost, figure: PublicFigure | None) -> dict:
    author = post.author_data or {}
    avatar = author.get('profile_image_url') or ''
    affiliation = party_affiliation(figure)
    return {
        'account_id': post.account_id,
        'name': display_name(clean_account_name(figure.canonical_name if figure else (author.get('name') or post.account.display_name))),
        'handle': post.account.handle,
        'account_url': f'https://x.com/{post.account.handle}',
        'avatar_url': avatar.replace('_normal.', '_bigger.') if avatar else '',
        'figure_id': figure.pk if figure else None,
        'role_title': figure.role_title if figure else '',
        'party': affiliation['party'],
        'eu_group': affiliation['eu_group'],
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
        'camp_at_collection': post.camp_at_collection,
        'published_at': timezone.localtime(post.published_at).strftime('%Y-%m-%d %H:%M'),
        'url': post.url,
        'text': post.text,
        'media_notes': ', '.join(media),
        'media': [item for item in post.media or [] if isinstance(item, dict)],
    }


def unscreened_posts(include_old=False):
    since = timezone.now() - timedelta(days=int(os.environ.get('CLINIC_MAX_POST_AGE_DAYS', '3')))
    rows = PoliticalPost.objects.filter(available=True, camp_at_collection__in=CAMPS, account__enabled=True).filter(
        Q(spin_diagnosis__isnull=True) | Q(spin_diagnosis__status='flagged', spin_diagnosis__screen_score__isnull=True,
                                          spin_diagnosis__diagnosed_at__isnull=True))
    if not include_old:
        rows = rows.filter(published_at__gte=since)
    return rows.select_related('account').order_by('fetched_at' if include_old else '-published_at', '-pk')


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
    from news.repairer import permanent
    from news.council_health import error_kind
    transient = {'429', 'timeout', 'daily_limit', 'too_few', 'connection', 'server'}
    return sum(error_kind(error) not in transient and permanent(error)
               for error in _anthropic_today().filter(status='failed').values_list('error', flat=True))


def _anthropic_today():
    start = local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    return SpinDiagnosis.objects.filter(diagnosed_at__gte=start, provider='anthropic')


def screen_post(post: PoliticalPost, retry=False) -> SpinDiagnosis | None:
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
                  'provider': result['provider'], 'model_name': str(result['model'])[:64]}
    try:
        with transaction.atomic():
            return SpinDiagnosis.objects.create(post=post, prompt_version=clinic_ai.PROMPT_VERSION, **fields)
    except IntegrityError:
        if retry and result is not None:
            changed = SpinDiagnosis.objects.filter(post=post, status='flagged', screen_score__isnull=True,
                diagnosed_at__isnull=True).update(**fields)
            if changed:
                return SpinDiagnosis.objects.get(post=post)
        return None


def run_screening(limit: int = 30, *, include_old=False, post_ids=None) -> dict:
    counts = {}
    posts = unscreened_posts(include_old=include_old)
    if post_ids is not None:
        posts = posts.filter(pk__in=post_ids)
    if not include_old:
        posts = posts.order_by('-watch_priority', '-published_at', '-pk')
    for post in posts[:limit]:
        row = screen_post(post, retry=True)
        if row:
            counts[row.status] = counts.get(row.status, 0) + 1
    alert = send_review_alert() if counts.get('flagged') else 'nothing'
    return {'screened': counts, 'alert': alert}


SNAPSHOT_DAYS = 7


def _snapshot(row: SpinDiagnosis) -> dict | None:
    """Zapisany wynik wcześniejszej, opłaconej diagnozy tego wpisu, której nie udało się zapisać w całości."""
    snap = (row.usage or {}).get('snapshot')
    taken = (row.usage or {}).get('snapshot_at')
    if not isinstance(snap, dict) or not taken:
        return None
    try:
        fresh = timezone.now() - datetime.fromisoformat(taken) < timedelta(days=SNAPSHOT_DAYS)
    except (TypeError, ValueError):
        return None
    return dict(snap) if fresh else None


def diagnose(row: SpinDiagnosis, figure: PublicFigure | None = None) -> SpinDiagnosis:
    """Płatna diagnoza jednego wpisu z kolejki. Wynik najpierw trafia do bazy jako „zdjęcie” (usage['snapshot']) — gdy
    pełny zapis się wywróci, kolejna próba bierze zdjęcie zamiast płacić za AI drugi raz (29–30.09.2026 ponawiane
    nieudane zapisy kosztowały ok. 135 zł)."""
    try:
        result = _snapshot(row)
        if result is None:
            result = clinic_ai.diagnose(_post_context(row.post, figure))
            # Zdjęcie: jedna mała aktualizacja samego pola JSON (bez limitów długości), zanim cokolwiek innego się zapisze.
            row.usage = {**(row.usage or {}), 'snapshot': result, 'snapshot_at': timezone.now().isoformat()}
            SpinDiagnosis.objects.filter(pk=row.pk).update(usage=row.usage)
        result = dict(result)
    except clinic_ai.ClinicAIError as error:
        if str(error.code).startswith('council_quorum'):
            return _defer_quorum(row, error)
        row.status, row.error = 'failed', error.code
        if hasattr(error, 'videos'):
            row.usage = {key: value for key, value in (row.usage or {}).items()
                         if key not in ('snapshot', 'snapshot_at')}
            row.usage['videos'] = error.videos
        if hasattr(error, 'council'):
            row.usage = {**(row.usage or {}), 'council': error.council}
        row.provider, row.model_name = 'anthropic', clinic_ai.model_name()
    else:
        if 'lab' not in result:
            from news.clinic_lab import run_lab
            result['lab'] = run_lab(row.post.text, result.get('claims', []), result.get('loaded_words'))
        usage = result.pop('usage', {})  # po udanym zapisie zdjęcie znika z usage — wynik jest już w kolumnach
        usage['loaded_words'] = result.pop('loaded_words', [])
        result.setdefault('plain', {})  # Ponowna diagnoza starym dostawcą nie zachowuje starego skrótu.
        for field, value in result.items():
            setattr(row, field, value)
        row.status, row.usage, row.error = ('approved' if auto_publish() else 'pending_review'), usage, ''
        if row.status == 'approved':
            row.reviewed_at = timezone.now()
        row.provider = 'anthropic'  # płatna diagnoza (Claude albo Gemini) — to pole odróżnia ją od strażnika
        # Pełny skład Konsylium jest w usage['council']; pole ma 64 znaki (lista nazw przy komplecie członków jest dłuższa).
        row.model_name = (usage.get('model') or clinic_ai.model_name())[:64]
    row.diagnosed_at = timezone.now()
    row.prompt_version = clinic_ai.PROMPT_VERSION
    try:
        with transaction.atomic():
            row.save()
    except DatabaseError as error:
        # Wynik jest bezpieczny w zdjęciu; wpis oznaczamy jako nieudany z przyczyną — kolejna próba nic nie kosztuje.
        logger.error('diagnosis %s: save failed, snapshot kept: %s', row.pk, error)
        SpinDiagnosis.objects.filter(pk=row.pk).update(status='failed', error=f'save_failed: {error}'[:240])
        row.status, row.error = 'failed', f'save_failed: {error}'[:240]
        return row
    if row.status in ('approved', 'pending_review'):
        from news.clinic_lab import queue_archive
        queue_archive(row.post)
        ensure_x_thread(row)
    return row


def _defer_quorum(row: SpinDiagnosis, error) -> SpinDiagnosis:
    """Brak kworum Konsylium: diagnoza się nie ukazuje, wpis czeka w kolejce (bez diagnosed_at - nie liczy się do
    dziennego limitu). Powód w error i usage['quorum']; ponowienie po resecie limitów albo po naprawie modelu."""
    from news import council_quorum
    now = timezone.now()
    council = getattr(error, 'council', None) or {}
    previous = (row.usage or {}).get('quorum') or {}
    usage = {key: value for key, value in (row.usage or {}).items() if key not in ('snapshot', 'snapshot_at')}
    if council:
        usage['council'] = council
    if hasattr(error, 'videos'):
        usage['videos'] = error.videos
    usage['quorum'] = {**(getattr(error, 'quorum', None) or {}), 'attempts': int(previous.get('attempts', 0)) + 1,
                       'first_at': previous.get('first_at') or now.isoformat(), 'last_at': now.isoformat()}
    row.status, row.error, row.usage = 'queued', str(error.code)[:240], usage
    SpinDiagnosis.objects.filter(pk=row.pk).update(status=row.status, error=row.error, usage=row.usage)
    council_quorum.block(council.get('members') or [], row.error, now)
    logger.info('diagnosis %s: waits for council quorum (%s)', row.pk, row.error)
    return row


def quorum_waiting():
    """Wpisy czekające na kworum Konsylium (dla Raportu pętli i kolejki)."""
    return SpinDiagnosis.objects.filter(status='queued', error__startswith='council_quorum')


def ensure_x_thread(row: SpinDiagnosis, save: bool = True) -> bool:
    """Synteza diagnozy do wątku na X — raz na diagnozę, darmowym modelem. Treści diagnozy nie zmienia."""
    if (row.x_thread and scan_data(row)['synthesis']) or not row.verdict:
        return False
    figure = figures_by_account([row.post.account_id]).get(row.post.account_id)
    try:
        result = clinic_ai.x_thread({
            'author': figure.canonical_name if figure else row.post.account.display_name,
            'verdict_label': VERDICT_LABELS.get(row.verdict, ''), 'intensity': row.intensity,
            'headline': row.headline, 'summary': row.summary, 'techniques': row.techniques,
            'claims': [{**claim, 'assessment_label': ASSESSMENT_LABELS.get(claim.get('assessment'), '')} for claim in row.claims],
        })
    except clinic_ai.ClinicAIError:
        return False
    row.x_thread = polish_synthesis(result['posts'])
    row.usage = {**(row.usage or {}), 'scan_synthesis': synthesis_fingerprint(row)}
    if save:
        row.save(update_fields=['x_thread', 'usage'])
    return True


def polish_synthesis(posts: list[str]) -> list[str]:
    """Synteza przechodzi przez językoznawcę Konsylium, jak treść diagnozy (limity X zachowane)."""
    from news.clinic_council import polish_lines
    limits = [clinic_ai.X_LEAD_CHARS + 20] + [clinic_ai.X_POINT_CHARS + 20] * (len(posts) - 1)
    return polish_lines(list(posts), limits)


def fill_x_threads(limit: int = 5) -> int:
    """Uzupełnia brakujące lub niesprawdzone syntezy z całego backlogu, od najstarszych."""
    rows = published_diagnoses().exclude(verdict='').order_by('diagnosed_at', 'pk')
    completed = attempted = 0
    for row in rows.iterator():
        if attempted >= max(0, limit):
            break
        if scan_data(row)['synthesis'] is None:
            attempted += 1
            completed += ensure_x_thread(row)
    return completed


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


def posts_spent_today() -> float:
    """Szacowane wydatki na Claude'a od północy — tylko diagnozy wpisów."""
    start = local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    return round(sum(clinic_ai.cost_usd(usage) for usage in
                     SpinDiagnosis.objects.filter(diagnosed_at__gte=start, provider='anthropic').values_list('usage', flat=True)), 4)


def interview_spent_today() -> float:
    """Szacowane wydatki od północy na diagnozę wywiadu dnia (Claude albo Gemini; transkrypcja nie jest liczona)."""
    from news.clinic_models import ClinicInterview
    start = local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    return round(sum(clinic_ai.cost_usd((usage or {}).get('claude') or {}) for usage in
                     ClinicInterview.objects.filter(diagnosed_at__gte=start).values_list('usage', flat=True)), 4)


def spent_today() -> float:
    """Szacowane wydatki od północy razem: diagnozy wpisów i wywiad dnia."""
    return round(posts_spent_today() + interview_spent_today(), 4)


def _env_usd(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, '') or default)
    except ValueError:
        return default


def budget_left() -> float:
    """Twardy dzienny budżet na płatne diagnozy WPISÓW (CLINIC_DAILY_BUDGET_USD, domyślnie 2 USD).
    Wywiad dnia ma osobny budżet (interview_budget_left) — nie zabiera pieniędzy wpisom (decyzja właściciela 28.09)."""
    return round(_env_usd('CLINIC_DAILY_BUDGET_USD', 2.0) - posts_spent_today(), 4)


def interview_budget_left() -> float:
    """Osobny dzienny budżet na diagnozę wywiadu dnia Claude'em (CLINIC_INTERVIEW_BUDGET_USD, domyślnie 3.5 USD).
    Gdy go brakuje, wywiad ocenia Gemini (darmowy limit) — patrz clinic_interview.diagnose_transcript."""
    return round(_env_usd('CLINIC_INTERVIEW_BUDGET_USD', 3.5) - interview_spent_today(), 4)


BUDGET_RESERVE_USD = 0.25  # dolna granica rezerwy; prawdziwa rezerwa liczona z kosztów ostatnich diagnoz


def diagnosis_reserve() -> float:
    """Ile musi zostać w budżecie, żeby zacząć diagnozę: najdroższa z ostatnich 15 diagnoz (min. 0,25 USD, maks. 3 USD).
    2.10.2026: przy stałej rezerwie 0,25 USD limit 5 USD przekroczono o 23% (pojedyncze diagnozy kosztowały do 1,51 USD)."""
    recent = SpinDiagnosis.objects.filter(provider='anthropic', diagnosed_at__isnull=False).order_by('-diagnosed_at').values_list('usage', flat=True)[:15]
    costs = [clinic_ai.cost_usd(usage or {}) for usage in recent]
    return round(min(3.0, max([BUDGET_RESERVE_USD, *costs])), 4)


def run_diagnoses(limit: int = 2) -> dict:
    """Płatne diagnozy rozłożone na dzień: zwykłe równo od rana do wieczora, a jedno miejsce czeka na
    najpopularniejszy post dnia (od CLINIC_FEATURED_HOUR) — to on zostaje spinem dnia."""
    if not clinic_ai.enabled():
        return {'status': 'disabled'}
    reserve = diagnosis_reserve()
    if budget_left() < reserve:
        return {'status': 'budget', 'spent_today_usd': spent_today(), 'reserve_usd': reserve}
    if failures_today() >= _env_int('CLINIC_DAILY_FAILURE_LIMIT', 5):
        # Seria błędów (klucz, model, limit konta) — nie palimy pieniędzy do jutra albo do naprawy.
        return {'status': 'too_many_failures', 'failed_today': failures_today()}
    now = local_now()
    start, end = day_window(now)
    if not start <= now < end:
        return {'status': 'night'}
    expire_quorum_waits()
    if clinic_ai.provider() == 'council':
        # Kworum przed zapytaniami (bez kosztów): przerwa po nieudanym kworum albo za mało wolnych członków - wpisy czekają.
        from news import council_quorum
        wait = council_quorum.waiting()
        state = None if wait else council_quorum.possible()
        if wait or not state['met']:
            return {'status': 'quorum', 'waiting': quorum_waiting().count(),
                    'reason': (wait or {}).get('reason') or state['reason'], 'until': (wait or {}).get('until', '')}
    daily = _env_int('CLINIC_DAILY_LIMIT', 8)
    reserve = 1 if daily > 1 else 0
    counts = {}
    featured = featured_today()
    if reserve and not featured and now.hour >= _env_int('CLINIC_FEATURED_HOUR', 18) and diagnoses_today() < daily:
        row = pick_featured()
        if row:
            figure = figures_by_account({row.post.account_id}).get(row.post.account_id)
            if budget_left() >= reserve:
                diagnose(row, figure)
            counts[f'featured_{row.status}'] = 1
    regular_done = diagnoses_today() - (1 if featured_today() else 0)
    take = max(0, min(limit, paced_target(now, daily - reserve) - regular_done))
    # Tylko świeże posty (domyślnie z ostatnich 24 h) — Klinika komentuje bieżące przekazy, nie archiwum.
    fresh = timezone.now() - timedelta(hours=_env_int('CLINIC_FRESH_HOURS', 24))
    # Wpisy czekające na kworum Konsylium wracają mimo okna świeżości (najwyżej council_quorum.MAX_WAIT_HOURS).
    from news.council_quorum import MAX_WAIT_HOURS
    waited = timezone.now() - timedelta(hours=MAX_WAIT_HOURS)
    rows = list(SpinDiagnosis.objects.filter(status='queued').filter(
        Q(post__published_at__gte=fresh) | Q(error__startswith='council_quorum', post__published_at__gte=waited))
                .select_related('post__account')
                .order_by('-post__watch_priority', '-screen_score', '-post__published_at')[:take])
    if auto_publish() and len(rows) < take:
        # Żeby spiny wpadały codziennie: gdy wysoko ocenionych postów brakuje, bierzemy najwyżej ocenione
        # z oznaczonych przez strażnika (z ostatniej doby), aż do dziennego limitu.
        extra = (SpinDiagnosis.objects.filter(status='flagged', screen_score__isnull=False, post__published_at__gte=fresh)
                 .select_related('post__account').order_by('-screen_score', '-post__published_at')[:take - len(rows)])
        rows += list(extra)
    figures = figures_by_account({row.post.account_id for row in rows})
    for row in rows:
        if budget_left() < reserve:
            counts['budget_stop'] = 1
            break
        diagnose(row, figures.get(row.post.account_id))
        counts[row.status] = counts.get(row.status, 0) + 1
        if row.status == 'queued':
            counts['quorum'] = 1
            break  # bez kworum kolejne wpisy też by czekały - nie zużywamy limitów członków
    alert = send_review_alert()
    return {'status': 'ok', 'budget_left': max(0, daily - diagnoses_today()), 'usd_left_today': budget_left(),
            'diagnosed': counts, 'alert': alert}


def expire_quorum_waits() -> int:
    """Wpis czekał na kworum dłużej niż MAX_WAIT_HOURS od publikacji: nieudany z powodem (nie znika bez śladu)."""
    from news.council_quorum import MAX_WAIT_HOURS
    old = quorum_waiting().filter(post__published_at__lt=timezone.now() - timedelta(hours=MAX_WAIT_HOURS))
    return old.update(status='failed', error=f'council_quorum_expired: brak kworum Konsylium przez {MAX_WAIT_HOURS} h')


MIN_MESSAGE_ACCOUNTS = 3


def run_daily_messages(day=None, *, camps=None, models=None, only_missing=False) -> dict:
    """Przekaz dnia każdego obozu — darmowe modele (Groq, zapasowo NIM, potem Mercury), z postów co najmniej trzech kont.

    W ciągu dnia przekaz jest odświeżany (9:00, 12:00, 15:00, 18:00, 21:30), dopóki nikt go ręcznie nie zatwierdził.
    Niepowodzenie zostaje w bazie jako wiersz failed z powodem; repair_daily_messages dorabia brakujące co godzinę.
    """
    created = {}
    if day is None:
        # Dogrywka (właściciel 3.10: brak przekazu opozycji z 2.10): gdy wczoraj żaden przebieg nie zapisał przekazu
        # obozu (np. limit darmowych modeli), próbujemy jeszcze raz dla wczoraj, zanim zrobimy dzisiejszy.
        yesterday = timezone.localdate() - timedelta(days=1)
        missing = [camp for camp in CAMPS if not ClinicDailyMessage.objects.filter(day=yesterday, camp=camp).exclude(status='failed').exists()]
        if missing:
            created.update({f'{yesterday.isoformat()}:{camp}': pk for camp, pk in _daily_messages_for(yesterday, missing).items()})
    day = day or timezone.localdate()
    errors = {}
    created.update(_daily_messages_for(day, camps or CAMPS, models=models, only_missing=only_missing, errors=errors))
    alert = send_review_alert()
    return {'status': 'error' if errors else 'ok', 'created': created, 'alert': alert, 'errors': errors}


def message_settled(day, camp) -> bool:
    """Przekaz jest: zapisany (approved / pending_review z treścią) albo rozstrzygnięty ręcznie (także odrzucony)."""
    return ClinicDailyMessage.objects.filter(day=day, camp=camp).filter(
        Q(reviewed_by__isnull=False) | (Q(status__in=('approved', 'pending_review')) & ~Q(message=''))).exists()


def repair_daily_messages(day=None) -> dict:
    """Naprawa co godzinę (10-23): tylko obozy bez przekazu albo z zapisanym błędem; gdy oba są - nic nie robi.
    Po przebiegu 21:30 dalszy brak przekazu to jeden mail do właściciela na obóz i dzień (naprawa sama nie pomogła)."""
    day = day or timezone.localdate()
    missing = [camp for camp in CAMPS if not message_settled(day, camp)]
    if not missing:
        return {'status': 'ok', 'created': {}, 'skipped': 'complete'}
    result = run_daily_messages(day, camps=missing, only_missing=True)
    result['owner_alerts'] = alert_owner_missing_messages(day)
    return result


def alert_owner_missing_messages(day, now=None) -> list:
    """Właściciel dostaje wiadomość dopiero, gdy po wieczornym przebiegu (21:30) przekaz dnia nadal nie powstał
    (zasada „najpierw naprawa automatyczna”). Powód z wiersza failed; alert_sent_at pilnuje jednego maila."""
    from news.council_recruiter import _owner_email
    from news.daily_schedule import at
    from news.social_publish import _mail
    now = now or timezone.now()
    if day != timezone.localdate(now) or now < at(now, 21, 30):
        return []
    sent = []
    for row in ClinicDailyMessage.objects.filter(day=day, status='failed', alert_sent_at__isnull=True):
        label = 'rządzący' if row.camp == 'government' else 'opozycja'
        body = (f'Przekaz dnia ({label}) za {day.isoformat()} nie powstał mimo prób co godzinę.\n'
                f'Ostatni powód: {row.error or "brak zapisanego powodu"}\n\n'
                'Kolejny przebieg naprawy spróbuje ponownie; przekaz można też uruchomić ręcznie:\n'
                "run_daily_messages(camps=('" + row.camp + "',))\n\nPanel: https://spin.clinic/panel")
        try:
            ok = _mail(_owner_email(), f'spin.clinic: brak przekazu dnia ({label}) {day.isoformat()}', body, important=True)
        except Exception:  # noqa: BLE001 - poczta nie może przerwać naprawy
            ok = False
        if ok:
            ClinicDailyMessage.objects.filter(pk=row.pk).update(alert_sent_at=now)
            sent.append(row.camp)
    return sent


def message_posts(day, camp):
    start = timezone.make_aware(datetime.combine(day, time.min))
    rows = PoliticalPost.objects.filter(
        available=True, camp_at_collection=camp, account__enabled=True,
        published_at__gte=start, published_at__lt=start + timedelta(days=1),
    ).exclude(spin_diagnosis__withdrawn_at__isnull=False)
    rows = rows.exclude(spin_diagnosis__hidden_at__isnull=False).select_related('account').order_by('-published_at')
    from news.message_stats import is_noise
    selected, per_account = [], {}
    substantive_count = 0
    for post in rows.iterator(chunk_size=200):
        if is_noise(post.text):
            selected.append(post)
            continue
        # Jedno aktywne konto nie może wyprzeć pozostałych autorów.
        if per_account.get(post.account_id, 0) >= clinic_ai.DAILY_POSTS_PER_AUTHOR:
            continue
        selected.append(post)
        per_account[post.account_id] = per_account.get(post.account_id, 0) + 1
        substantive_count += 1
        if substantive_count == 60:
            break
    return selected


def _daily_messages_for(day, camps, *, models=None, only_missing=False, errors=None) -> dict:
    from django.core.cache import cache
    from uuid import uuid4
    from news.repairer import compare_delete
    created = {}
    for camp in camps:
        key, token = f'clinic-message:{day}:{camp}', uuid4().hex
        if not cache.add(key, token, 900):
            if errors is not None:
                errors[f'{day}:{camp}'] = 'Przekaz jest już opracowywany przez inny przebieg.'
            continue
        try:
            created.update(_message_for(day, (camp,), models=models, only_missing=only_missing, errors=errors))
        finally:
            compare_delete(key, token)
    return created


MESSAGE_ERROR_LABELS = {
    'free_models_unavailable': 'Darmowe modele nie odpowiedziały.',
    'daily_message_paid_budget': 'Wyłączony lub wyczerpany limit płatnego zapasu.',
    'not_polish': 'Model nie odpowiedział po polsku.', 'empty_message': 'Pusta odpowiedź modelu.',
    'invalid_message_structure': 'Odpowiedź modelu nie pasuje do wpisów.',
    'gemini_missing_key': 'Brak klucza Gemini.', 'gemini_daily_budget': 'Wyczerpany limit Gemini.',
    'inception_free_budget': 'Wyczerpana darmowa pula Inception (Mercury).',
    'inception_daily_limit': 'Dzienny pułap Inception (Mercury) wykorzystany.',
    'inception_halted': 'Inception (Mercury) zatrzymany do zmiany klucza.',
}


def message_error_label(code: str) -> str:
    from news.admin_telemetry import safe_error
    if code in MESSAGE_ERROR_LABELS:
        return MESSAGE_ERROR_LABELS[code]
    if code.startswith('inception'):
        return 'Inception (Mercury) nie odpowiedział.'
    return safe_error(code).replace('—', '-')


def _message_for(day, camps, *, models=None, only_missing=False, errors=None) -> dict:
    created = {}
    for camp in camps:
        existing = ClinicDailyMessage.objects.filter(day=day, camp=camp).first()
        if existing and (existing.reviewed_by_id or (only_missing and existing.message and existing.status in ('approved', 'pending_review'))):
            continue  # zatwierdzony ręcznie — nie nadpisujemy
        from news.message_stats import calculate_stats, is_noise, post_rows
        posts = message_posts(day, camp)
        rows = post_rows(posts)
        _, material = clinic_ai._daily_material(CAMP_PROMPT_LABELS[camp], day.isoformat(), rows)
        included = {row['id'] for row in material}
        posts = [post for post in posts if str(post.pk) in included or is_noise(post.text)]
        rows = [row for row in rows if row['id'] in included or is_noise(row['text'])]
        if len({row['author_id'] for row in material}) < MIN_MESSAGE_ACCOUNTS:
            continue
        try:
            options = {'models': models} if models is not None else {}
            result = clinic_ai.daily_message(CAMP_PROMPT_LABELS[camp], day.isoformat(), material, **options)
        except clinic_ai.ClinicAIError as error:
            logger.warning('clinic daily message failed: %s', error.code)
            label = message_error_label(error.code)
            if errors is not None:
                errors[f'{day}:{camp}'] = label
            # Powód zostaje w bazie (wiersz failed bez treści), ale nigdy nie zastępuje już zapisanego przekazu.
            if existing is None or existing.status == 'failed':
                ClinicDailyMessage.objects.update_or_create(day=day, camp=camp, defaults={
                    'message': '', 'status': 'failed', 'error': f'{error.code}: {label}'[:300],
                    'prompt_version': clinic_ai.PROMPT_VERSION, 'created_at': timezone.now()})
            continue
        status = 'approved' if auto_publish() else 'pending_review'
        message, _ = ClinicDailyMessage.objects.update_or_create(day=day, camp=camp, defaults={
            'message': result['message'], 'analysis': result.get('analysis', ''), 'themes': result['themes'],
            'thesis': result.get('thesis', ''), 'points': result.get('points', []), 'tone': result.get('tone', []),
            'stats': calculate_stats(rows, result.get('points'), result.get('tone')),
            'usage': result['usage'], 'status': status, 'error': '', 'alert_sent_at': None,
            'model_name': result['usage'].get('model', '')[:64], 'prompt_version': clinic_ai.PROMPT_VERSION,
            'reviewed_at': timezone.now() if status == 'approved' else None})
        message.posts.set(posts)
        created[camp] = message.pk
    return created


# --- alerty ---------------------------------------------------------------------------------

def staff_mail_enabled() -> bool:
    """Maile wewnętrzne do zespołu (alerty, raporty agentów, filmy do TikToka). Domyślnie wyłączone (właściciel 2.10.2026:
    za dużo wiadomości na admin@spin.clinic). Włączenie: STAFF_MAIL_ENABLED=true. Maile do czytelników działają bez zmian."""
    return os.environ.get('STAFF_MAIL_ENABLED', 'false').strip().lower() in ('1', 'true', 'yes')


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
    if recipient and staff_mail_enabled() and _smtp_ready():
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

@transaction.atomic
def withdraw(diagnosis, staff, reason):
    """Wycofuje publikację atomowo; zapisane wyniki AI pozostają nietknięte."""
    if not staff or not staff.is_active or not staff.is_staff:
        raise PermissionError('Wycofanie wymaga uprawnień zespołu.')
    reason = reason.strip() if isinstance(reason, str) else ''
    if not reason or len(reason) > 400:
        raise ValueError('Podaj powód wycofania (od 1 do 400 znaków).')
    current = SpinDiagnosis.objects.select_for_update().get(pk=diagnosis.pk)
    if current.status != 'approved' or current.withdrawn_at:
        raise ValueError('Można wycofać tylko opublikowaną diagnozę.')
    current.status = 'withdrawn'
    current.withdrawn_at, current.withdrawn_by, current.withdrawn_reason = timezone.now(), staff, reason
    current.save(update_fields=['status', 'withdrawn_at', 'withdrawn_by', 'withdrawn_reason'])
    diagnosis.refresh_from_db()
    return diagnosis


def published_diagnoses():
    return (SpinDiagnosis.objects.filter(status='approved', withdrawn_at__isnull=True, hidden_at__isnull=True, post__available=True)
            .select_related('post__account'))


def published_messages():
    # Synteza może nadal cytować wycofany materiał: wyłączamy cały przekaz.
    unavailable = SpinDiagnosis.objects.filter(Q(withdrawn_at__isnull=False) | Q(hidden_at__isnull=False))
    return ClinicDailyMessage.objects.filter(status='approved').exclude(posts__spin_diagnosis__in=unavailable)


def _media(post: PoliticalPost) -> list[dict]:
    result = []
    for item in post.media or []:
        if not isinstance(item, dict):
            continue
        url = item.get('url') or item.get('thumbnail_url') or item.get('preview_image_url')
        if url:
            result.append({'type': item.get('type', 'photo'), 'url': url, 'alt': item.get('alt_text', '')})
    return result[:4]


def card_data(diagnosis: SpinDiagnosis, figures: dict, counts: dict | None = None, comment_count: int | None = None) -> dict:
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
        'technique_types': [{key: item[key] for key in ('name', 'category', 'family') if key in item}
                            for item in diagnosis.techniques],
        'claims': [{'assessment': clean_claim(item).get('assessment', 'unverified')} for item in diagnosis.claims],
        'council': ({'members': [{key: member.get(key) for key in ('model', 'verdict', 'intensity', 'status')}
                                  for member in (diagnosis.usage['council'].get('members') or [])]}
                    if (diagnosis.usage or {}).get('council') is not None else None),
        'technique_groups': technique_groups(diagnosis.techniques),
        'scan': scan_data(diagnosis),
        'post': {'id': post.post_id, 'url': post.url, 'text': post.text, 'published_at': post.published_at,
                 'available': post.available,
                 'media': _media(post), 'likes': metrics.get('like_count', 0), 'reposts': metrics.get('retweet_count', 0)},
        'author': author_data(post, figures.get(post.account_id)),
        'opinions': counts or {'positive': 0, 'negative': 0},
        # Bez zapytania do bazy: liczbę komentarzy podaje wywołujący (lista, strona diagnozy); obrazki jej nie potrzebują.
        'comment_count': comment_count or 0,
    }


def detail_data(diagnosis: SpinDiagnosis) -> dict:
    from news.clinic_corrections import withdrawn_data
    if diagnosis.hidden_at:
        raise ValueError('Diagnoza ukryta po zgłoszeniu prawnym.')
    if diagnosis.withdrawn_at:
        return withdrawn_data(diagnosis)
    figures = figures_by_account([diagnosis.post.account_id])
    counts = {'positive': 0, 'negative': 0}
    counts.update({row['polarity']: row['n'] for row in diagnosis.opinions.filter(polarity__isnull=False).values('polarity').annotate(n=Count('id'))})
    data = card_data(diagnosis, figures, counts, diagnosis.comments.count())
    data.update({
        'analysis': diagnosis.analysis,
        'plain': diagnosis.plain,
        'lab': diagnosis.lab,
        'techniques': diagnosis.techniques,
        'claims': [{**claim, 'assessment_label': ASSESSMENT_LABELS.get(claim.get('assessment'), '')}
                   for claim in (clean_claim(item) for item in diagnosis.claims)],
        'limitations': diagnosis.limitations,
        # redakcja językowa (sens bez zmian): jawna, z tekstem pierwotnym (właściciel 5.10)
        'readability_edit': {'at': (diagnosis.usage or {}).get('readability_edit', {}).get('at'), 'original': (diagnosis.usage or {}).get('original_text', {})} if (diagnosis.usage or {}).get('readability_edit') else None,
        'x_thread': diagnosis.x_thread,
        'council': (diagnosis.usage or {}).get('council'),
        # Powtórka po pełnym składzie Konsylium (news/council_rerun.py): poprzednie wyniki jawnie, nic nie znika.
        'revisions': [{key: item.get(key) for key in ('at', 'verdict', 'intensity', 'members', 'reason')}
                      for item in (diagnosis.usage or {}).get('history') or []],
        'model': diagnosis.model_name,
        'prompt_version': diagnosis.prompt_version,
        'created_at': diagnosis.created_at,
        'reviewed_at': diagnosis.reviewed_at,
        'auto_published': diagnosis.status == 'approved' and not diagnosis.reviewed_by_id,
        'notice': NOTICE,
        'status': 'approved',
        'author_replies': list(diagnosis.author_replies.filter(published_at__lte=timezone.now()).values(
            'id', 'body', 'source_url', 'received_at', 'published_at')),
    })
    # Raport źródeł 6.10: kopie cytowanych artykułów (Wayback) i „Tę tezę sprawdzili” (Google Fact Check)
    from news import fakty, straznik_mediow
    urls = [s.get('url', '') for c in diagnosis.claims or [] if isinstance(c, dict) for s in c.get('sources') or [] if isinstance(s, dict)]
    data['source_archives'] = straznik_mediow.archives_for(urls)
    data['factchecks'] = fakty.public(diagnosis)
    from news.zmiana_zdania import public_data as position_changes
    data['position_changes'] = position_changes(diagnosis)  # Zmiana zdania: tylko pary powyżej progu, ten sam dla każdej partii
    from news.odbior_spinu import public_data as reception
    data['reception'] = reception(diagnosis)  # Jak zadziałało (po 24 h): liczby zbiorcze, bez danych osób prywatnych
    from news.x_share import build
    data['x_share'] = build(data)
    return data


def _opinion_counts(ids) -> dict[int, dict]:
    from news.clinic_models import SpinOpinion
    result = {pk: {'positive': 0, 'negative': 0} for pk in ids}
    for row in SpinOpinion.objects.filter(diagnosis_id__in=ids, polarity__isnull=False).values('diagnosis_id', 'polarity').annotate(n=Count('id')):
        result[row['diagnosis_id']][row['polarity']] = row['n']
    return result


def cards(queryset) -> list[dict]:
    rows = list(queryset)
    figures = figures_by_account({row.post.account_id for row in rows})
    counts = _opinion_counts([row.pk for row in rows])
    from news.clinic_discussion_models import ClinicComment
    comments = dict(ClinicComment.objects.filter(diagnosis_id__in=counts).values('diagnosis_id').annotate(n=Count('id')).values_list('diagnosis_id', 'n'))
    return [card_data(row, figures, counts[row.pk], comments.get(row.pk, 0)) for row in rows]


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


def _message_data(message: ClinicDailyMessage, with_posts: bool = False, *, all_posts: bool = False) -> dict:
    data = {'id': message.pk, 'day': message.day, 'camp': message.camp, 'message': message.message,
            'analysis': message.analysis, 'themes': message.themes,
            'comment_count': message.comments.count(),
            'opinions': {'positive': message.opinions.filter(polarity='positive').count(), 'negative': message.opinions.filter(polarity='negative').count()},
            'thesis': message.thesis, 'points': message.points, 'stats': message.stats, 'posts_count': message.posts.count(),
            'model': message.model_name, 'created_at': message.created_at, 'reviewed_at': message.reviewed_at,
            'readability_edit': {'original': (message.usage or {}).get('original_text', {})} if (message.usage or {}).get('readability_edit') else None}
    if with_posts:
        data['scope'] = {**message.posts.aggregate(date_from=Min('published_at'), date_to=Max('published_at')),
                         'timezone': str(timezone.get_current_timezone())}
        # Źródła przekazu: posty, z których powstał (autor, link do X, fragment treści).
        rows = message.posts.select_related('account').order_by('-published_at', '-pk')
        posts = list(rows if all_posts else rows[:60])
        figures = figures_by_account({post.account_id for post in posts})
        data['posts'] = [{'id': str(post.pk), 'url': post.url, 'text': post.text[:280] if post.available else '',
                          'available': post.available, 'published_at': post.published_at,
                          'author': (figures[post.account_id].canonical_name if post.account_id in figures
                                     else post.account.display_name), 'handle': post.account.handle} for post in posts]
    return data


def daily_message_data(camp: str):
    message = published_messages().filter(camp=camp).order_by('-day').first()
    return _message_data(message, with_posts=True) if message else None


def message_history(days: int = 30) -> dict:
    """Wcześniejsze przekazy dnia każdego obozu — od najnowszych."""
    return {camp: [_message_data(message) for message in
                   published_messages().filter(camp=camp).order_by('-day')[:days]]
            for camp in CAMPS}


def spin_of_day():
    """Spin dnia: diagnoza z najwyższą siłą spinu wśród postów z dzisiaj; gdy dziś jeszcze nic — z ostatniej doby."""
    base = published_diagnoses().filter(verdict__in=['spin', 'partial'])
    now = timezone.now()
    today = local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    best = base.filter(post__published_at__gte=today).order_by('-intensity', '-post__published_at').first()
    if best:
        return detail_data(best)
    for hours in (24, 72):
        best = base.filter(post__published_at__gte=now - timedelta(hours=hours)).order_by('-intensity', '-post__published_at').first()
        if best:
            return detail_data(best)
    return None


def spin_of_day_by_camp() -> dict:
    """Spin dnia każdej strony — ta sama reguła co spin_of_day (najwyższa siła spinu wśród dzisiejszych postów,
    potem z ostatniej doby i trzech dni), a gdy strona nie ma świeżego spinu — jej najnowszy spin z datą.
    Kolejność zakładek: strona z mocniejszym spinem pierwsza (decyzja właściciela 28.09 — ocenia się wpis, nie stronę)."""
    base = published_diagnoses().filter(verdict__in=['spin', 'partial'])
    now = timezone.now()
    today = local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    picks = {}

    def first_checked(queryset):
        # Na wizytówkę tylko pełna usługa: pomijamy diagnozy, w których sprawdzanie faktów się nie odbyło.
        for row in queryset[:20]:
            if not check_failed([clean_claim(item) for item in row.claims]):
                return row
        return None

    for camp in CAMPS:
        rows = base.filter(post__camp_at_collection=camp)
        best, window = None, ''
        for label, since in (('today', today), ('24h', now - timedelta(hours=24)), ('72h', now - timedelta(hours=72))):
            best = first_checked(rows.filter(post__published_at__gte=since).order_by('-intensity', '-post__published_at'))
            if best:
                window = label
                break
        if best is None:
            best, window = rows.order_by('-diagnosed_at', '-pk').first(), 'latest'
        pool = published_diagnoses().filter(post__camp_at_collection=camp)
        if window != 'latest':
            pool = pool.filter(post__published_at__gte=since)
        labels = {'today': 'dzisiaj', '24h': 'ostatnia doba', '72h': 'ostatnie trzy doby',
                  'latest': 'całe archiwum; najnowszy spin'}
        picks[camp] = {**detail_data(best), 'window': window, 'pool': pool.count(),
                       'window_label': labels[window]} if best else None
    fresh = {'today': 3, '24h': 2, '72h': 1, 'latest': 0}
    order = sorted(CAMPS, key=lambda camp: (-(fresh[picks[camp]['window']] if picks[camp] else -1),
                                             -(picks[camp]['intensity'] if picks[camp] else -1)))
    return {'spins': picks, 'order': order}


def latest_spin(exclude_id: int | None = None):
    """Najnowszy spin — inny niż spin dnia, żeby przełącznik zawsze pokazywał drugi wpis."""
    rows = published_diagnoses().filter(verdict__in=['spin', 'partial'])
    if exclude_id:
        rows = rows.exclude(pk=exclude_id)
    latest = rows.order_by('-diagnosed_at', '-pk').first()
    return detail_data(latest) if latest else None


def clinic_stats() -> dict:
    """Liczniki pracy Kliniki: przeczytane posty, ocenione i odrzucone przez strażnika, opublikowane diagnozy i spiny.

    Każda liczba: łącznie od startu i dziś (od północy czasu polskiego). Pięć minut w pamięci podręcznej.
    """
    from django.core.cache import cache
    cached = cache.get('clinic-stats:v3')
    if cached is not None:
        return cached
    today = local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    screened = SpinDiagnosis.objects.all()
    published = published_diagnoses()
    spins = published.filter(verdict__in=['spin', 'partial'])

    def pair(total_qs, today_qs):
        return {'total': total_qs.count(), 'today': today_qs.count()}

    result = {
        **clinic_data_period(),
        'read': pair(PoliticalPost.objects.all(), PoliticalPost.objects.filter(fetched_at__gte=today)),
        'screened': pair(screened, screened.filter(created_at__gte=today)),
        'rejected': pair(screened.filter(status='not_applicable'), screened.filter(status='not_applicable', created_at__gte=today)),
        'diagnosed': pair(published, published.filter(diagnosed_at__gte=today)),
        'spins': pair(spins, spins.filter(diagnosed_at__gte=today)),
        # Obie strony obok siebie (pasek „ta sama miara” na głównej): konta, przeczytane wpisy, diagnozy, spiny.
        'by_camp': {camp: {
            'accounts': reading_accounts().filter(camp=camp).count(),
            'read': PoliticalPost.objects.filter(camp_at_collection=camp).count(),
            'diagnosed': published.filter(post__camp_at_collection=camp).count(),
            'spins': spins.filter(post__camp_at_collection=camp).count(),
        } for camp in CAMPS},
    }
    cache.set('clinic-stats:v3', result, 300)
    return result


def clinic_data_period() -> dict:
    """Zakres pracy od pierwszego odczytu lub publicznej diagnozy; nie data wpisu na X."""
    first_read = PoliticalPost.objects.aggregate(first=Min('fetched_at'))['first']
    first_diagnosis = published_diagnoses().aggregate(first=Min('diagnosed_at'))['first']
    moments = [stamp for stamp in (first_read, first_diagnosis) if stamp is not None]
    return {'generated_at': timezone.now().isoformat(),
            'since': timezone.localdate(min(moments)).isoformat() if moments else None}


def clinic_page_data(window_days: int = 7, per_camp: int = 20) -> dict:
    from news.clinic_interview import interview_archive, latest_interview_data, second_interview_data
    sotd = spin_of_day()
    columns = {camp: cards(published_diagnoses().filter(post__camp_at_collection=camp)
                           .order_by('-post__published_at', '-pk')[:per_camp]) for camp in CAMPS}
    stats = clinic_stats()
    return {
        'generated_at': stats['generated_at'], 'since': stats['since'],
        'notice': NOTICE_AUTO if auto_publish() else NOTICE_REVIEW,
        'scale': scale_data(window_days),
        'stats': stats,
        'messages': {camp: daily_message_data(camp) for camp in CAMPS},
        'spin_of_day': sotd,
        'spin_by_camp': spin_of_day_by_camp(),
        'latest_spin': latest_spin(sotd['id'] if sotd else None),
        'interview': latest_interview_data(),
        'interview_second': second_interview_data(),
        'interview_archive': interview_archive(),
        'message_history': message_history(),
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
    # Licznik na polityka: posty sprawdzone przez strażnika, częściowe spiny i spiny (opublikowane diagnozy).
    screened = dict(SpinDiagnosis.objects.filter(post__account__in=accounts).values_list('post__account_id').annotate(n=Count('id')))
    verdicts = {}
    for account_id, verdict, n in (published_diagnoses().filter(post__account__in=accounts, verdict__in=['spin', 'partial'])
                                   .values_list('post__account_id', 'verdict').annotate(n=Count('id'))):
        verdicts.setdefault(account_id, {})[verdict] = n
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
        'posts_screened': screened.get(account.pk, 0),
        'partial_spins': verdicts.get(account.pk, {}).get('partial', 0),
        'spins': verdicts.get(account.pk, {}).get('spin', 0),
        'last_polled_at': account.last_polled_at,
    } for account in accounts]
