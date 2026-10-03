"""Daily candidates and votes. Public reads never contact YouTube or a model."""
import html
import re
from datetime import datetime, time, timedelta
from urllib.parse import parse_qs, urlparse

from django.core.cache import cache
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import PermissionDenied, ValidationError

from news import clinic_interview as interviews
from news.account_models import AccountIdentity
from news.daily_schedule import WARSAW
from news.features import accounts_enabled
from news.interview_vote_models import InterviewBallot, InterviewCandidate, InterviewSubmission, InterviewVote


def closing_at(day):
    return datetime.combine(day + timedelta(days=1), time(7), tzinfo=WARSAW)


def yesterday():
    return timezone.now().astimezone(WARSAW).date() - timedelta(days=1)


def check_open(day):
    now = timezone.now().astimezone(WARSAW)
    if now >= closing_at(day):
        raise ValidationError('Głosowanie na ten dzień zakończyło się o 7:00.')
    if day > now.date():
        raise ValidationError('Głosowanie na ten dzień jeszcze się nie rozpoczęło.')


def lock_ballot(day):
    ballot, _ = InterviewBallot.objects.get_or_create(day=day)
    return InterviewBallot.objects.select_for_update().get(pk=ballot.pk)


def lock_verified(user):
    if not accounts_enabled() or not user.is_authenticated or not user.is_active:
        raise PermissionDenied('Zaloguj się, żeby głosować.')
    identity = AccountIdentity.objects.select_for_update().filter(user=user, email_verified=True).first()
    if not identity:
        raise PermissionDenied('Potwierdź e-mail, żeby głosować i dodawać wywiady.')


def youtube_id(url):
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ('https', 'http'):
            return None
        if parsed.hostname in ('youtu.be', 'www.youtu.be'):
            vid = parsed.path.strip('/')
        elif parsed.hostname in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
            parts = parsed.path.strip('/').split('/')
            vid = (parse_qs(parsed.query).get('v') or [''])[0] if parts == ['watch'] else (
                parts[1] if len(parts) == 2 and parts[0] in ('live', 'shorts', 'embed') else '')
        else:
            return None
        return vid if re.fullmatch(r'[A-Za-z0-9_-]{11}', vid) else None
    except ValueError:
        return None


def guest_details(title, description=''):
    """Same surname stems as the existing ranking, with canonical labels where available.

    Prefer the title: descriptions often list unrelated politicians in channel footers.
    No party/camp filter is applied.
    """
    from news.political_models import PublicFigure
    stems = set(interviews._politician_names()) | set(interviews._top_politicians())
    text = title.lower()
    keys = sorted(stem for stem in stems if re.search(rf'(?<!\w){re.escape(stem)}', text))
    if not keys:
        text = description.lower()
        keys = sorted(stem for stem in stems if re.search(rf'(?<!\w){re.escape(stem)}', text))
    labels = set(PublicFigure.objects.values_list('canonical_name', flat=True)) | interviews._politician_full_names()
    names = [name for name in sorted(labels)
             if any(re.search(rf'(?<!\w){re.escape(stem)}', name.lower()) for stem in keys)]
    return ', '.join(dict.fromkeys(names))[:300], keys


def candidate_fields(row):
    name, keys = guest_details(row['title'], row.get('description', ''))
    return {key: row.get(key, default) for key, default in (
        ('title', ''), ('description', ''), ('channel', ''), ('duration', 0), ('views', 0),
        ('score', 0), ('loudness', 0), ('top', False))} | {'guest_name': name, 'guest_keys': keys}


def refresh_candidates(day, *, recovery=False):
    """Scheduled scans only. Freeze at 7; a missing ballot can be recovered without votes."""
    if timezone.now() >= closing_at(day) and not recovery:
        return 0
    rows = interviews.rank_interviews(day)
    with transaction.atomic():
        ballot = lock_ballot(day)
        if timezone.now() >= closing_at(day) and (not recovery or ballot.candidates.exists()):
            return ballot.candidates.count()
        for row in rows:
            InterviewCandidate.objects.update_or_create(ballot=ballot, video_id=row['video_id'],
                defaults=candidate_fields(row) | {'from_ranking': True})
        ballot.refreshed_at = timezone.now()
        ballot.save(update_fields=['refreshed_at'])
        return ballot.candidates.count()


def validate_video(vid, day):
    key = f'interview-video:{vid}'
    items = cache.get(key)
    if items is None:
        try:
            items = interviews._yt('videos', part='snippet,contentDetails,statistics', id=vid).get('items') or []
        except interviews.clinic_ai.ClinicAIError:
            raise ValidationError('Nie można teraz sprawdzić filmu w YouTube. Spróbuj później.')
        cache.set(key, items, 900)
    if not items:
        raise ValidationError('Film nie istnieje lub nie jest publicznie dostępny.')
    item = items[0]
    snippet = item.get('snippet') or {}
    published = parse_datetime(snippet.get('publishedAt', ''))
    if not published or timezone.is_naive(published) or published.astimezone(WARSAW).date() != day:
        raise ValidationError('Film musi być opublikowany w wybranym dniu (czas Warszawy).')
    duration = interviews._duration_seconds((item.get('contentDetails') or {}).get('duration', ''))
    if duration < interviews.MIN_SECONDS:
        raise ValidationError('Wywiad musi trwać co najmniej 8 minut.')
    title, description = html.unescape(snippet.get('title', '')), html.unescape(snippet.get('description', ''))
    text = f'{title} {description}'
    # Database surnames + explicit talk signal, with no classifier or paid model.
    if not interviews.talk_signal(text, '', set(interviews._politician_names())):
        raise ValidationError('Tytuł lub opis musi wskazywać rozmowę z politykiem z naszej bazy.')
    stats = item.get('statistics') or {}
    views = int(stats.get('viewCount', 0))
    loudness = views + 20 * int(stats.get('commentCount', 0)) + 5 * int(stats.get('likeCount', 0))
    top = any(name in text.lower() for name in interviews._top_politicians())
    return candidate_fields({'title': title[:300], 'description': description, 'channel': snippet.get('channelTitle', '')[:200],
        'duration': duration, 'views': views, 'loudness': loudness, 'score': loudness * (3 if top else 1), 'top': top})


def check_submission_limit(user, ballot, candidate):
    if candidate and InterviewSubmission.objects.filter(user=user, candidate=candidate).exists():
        return
    if InterviewSubmission.objects.filter(user=user, candidate__ballot=ballot).count() >= 3:
        raise ValidationError('Możesz dodać najwyżej 3 wywiady na jeden dzień.')


def add_candidate(user, day, url):
    vid = youtube_id(url)
    if not vid:
        raise ValidationError('Wklej poprawny link do filmu w YouTube.')
    # Reject exhausted quotas before spending a YouTube unit; recheck after the request.
    with transaction.atomic():
        ballot = lock_ballot(day)
        lock_verified(user)
        check_open(day)
        candidate = ballot.candidates.filter(video_id=vid).first()
        check_submission_limit(user, ballot, candidate)
    fields = None if candidate else validate_video(vid, day)
    with transaction.atomic():
        ballot = lock_ballot(day)
        lock_verified(user)
        check_open(day)
        candidate = ballot.candidates.filter(video_id=vid).first()
        check_submission_limit(user, ballot, candidate)
        if not candidate:
            candidate = ballot.candidates.create(video_id=vid, **fields)
        InterviewSubmission.objects.get_or_create(user=user, candidate=candidate)
        return candidate


def cast_vote(user, day, candidate_id):
    with transaction.atomic():
        ballot = lock_ballot(day)
        lock_verified(user)
        check_open(day)
        candidate = ballot.candidates.filter(pk=candidate_id).first()
        if not candidate:
            raise ValidationError('Nie ma takiego kandydata na wybrany dzień.')
        InterviewVote.objects.update_or_create(user=user, ballot=ballot, defaults={'candidate': candidate})


def ballot_data(day, user):
    rows = InterviewCandidate.objects.filter(ballot__day=day).annotate(vote_count=Count('votes')).order_by('-vote_count', '-views', 'video_id')
    mine = InterviewVote.objects.filter(ballot__day=day, user=user).values_list('candidate_id', flat=True).first() if user.is_authenticated else None
    return {'day': day.isoformat(), 'closes_at': closing_at(day).isoformat(),
        'open': day <= timezone.now().astimezone(WARSAW).date() and timezone.now() < closing_at(day),
        'accounts_enabled': accounts_enabled(), 'mine': mine,
        'results': [{'id': row.pk, 'video_id': row.video_id, 'title': row.title, 'guest_name': row.guest_name,
            'channel': row.channel, 'duration': row.duration, 'views': row.views, 'votes': row.vote_count,
            'thumbnail_url': f'https://i.ytimg.com/vi/{row.video_id}/mqdefault.jpg'} for row in rows]}


def ranked_candidates(day):
    if not InterviewCandidate.objects.filter(ballot__day=day).exists():
        refresh_candidates(day, recovery=True)
    return InterviewCandidate.objects.filter(ballot__day=day).annotate(vote_count=Count('votes')).order_by('-vote_count', '-score', '-views', 'video_id')


def previous_guest_keys(day):
    from news.clinic_models import ClinicInterview
    previous = ClinicInterview.objects.filter(day=day - timedelta(days=1),
        status__in=['queued', 'flagged', 'pending_review', 'approved'], hidden_at__isnull=True).order_by('created_at').first()
    if not previous:
        return set(), ''
    saved = InterviewCandidate.objects.filter(ballot__day=previous.day, video_id=previous.video_id).first()
    _, keys = guest_details(previous.guest_name or previous.title)
    return set(keys) | set(saved.guest_keys if saved else []), previous.guest_name.casefold().strip()


def selection_label(interview):
    if interview.selection_method == 'votes':
        return f'Wybrany głosami czytelników ({interview.selection_votes} głosów)'
    if interview.selection_method == 'tie':
        return f'Wybrany według wyświetleń (remis: {interview.selection_votes} głosów)'
    if interview.selection_method == 'views':
        return 'Wybrany według wyświetleń (brak głosów)'
    return ''
