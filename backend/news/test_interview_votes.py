from datetime import date, datetime, timedelta
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from news import clinic_interview as interviews, interview_votes as votes
from news.account_models import AccountIdentity
from news.clinic_models import ClinicInterview
from news.daily_schedule import BEAT_PLAN, WARSAW, MILESTONES
from news.interview_vote_models import InterviewBallot, InterviewCandidate, InterviewSubmission, InterviewVote

pytestmark = pytest.mark.django_db
DAY = date(2026, 10, 2)
NOW = datetime(2026, 10, 3, 6, 30, tzinfo=WARSAW)
URL = '/api/clinic/interviews/voting/'


@pytest.fixture(autouse=True)
def isolated(settings, monkeypatch):
    cache.clear()
    monkeypatch.setenv('INTERVIEW_MIN_ACCOUNT_DAYS', '0')
    settings.ACCOUNTS_ENABLED = True
    monkeypatch.setattr(timezone, 'now', lambda: NOW)
    monkeypatch.setattr('requests.sessions.Session.request', Mock(side_effect=AssertionError('Bez prawdziwego HTTP')))
    monkeypatch.setattr(interviews, '_politician_names', lambda: ['nowak', 'kowalsk'])
    monkeypatch.setattr(interviews, '_politician_full_names', lambda: {'Jan Nowak', 'Anna Kowalska'})
    monkeypatch.setattr(interviews, 'enabled', lambda: True)
    monkeypatch.setattr(interviews, 'looks_like_interview', lambda *a: (True, ''))
    monkeypatch.setattr(interviews, 'rank_interviews', Mock(return_value=[]))
    yield
    cache.clear()


@pytest.fixture
def users():
    result = []
    for i in range(5):
        user = get_user_model().objects.create_user(f'voter{i}', email=f'voter{i}@example.org')
        AccountIdentity.objects.create(user=user, email=user.email, email_verified=True)
        result.append(user)
    return result


def video(**changes):
    result = {'id': 'a' * 11, 'snippet': {'title': 'Rozmowa z Janem Nowakiem', 'description': '',
        'publishedAt': '2026-10-02T14:00:00Z', 'channelTitle': 'Kanał'},
        'contentDetails': {'duration': 'PT8M'}, 'statistics': {'viewCount': '100'}}
    for section, fields in changes.items():
        result[section].update(fields)
    return result


def yt(monkeypatch, items=None):
    mock = Mock(return_value={'items': [video()] if items is None else items})
    monkeypatch.setattr(interviews, '_yt', mock)
    return mock


def candidate(letter='a', day=DAY, **fields):
    ballot, _ = InterviewBallot.objects.get_or_create(day=day)
    return InterviewCandidate.objects.create(ballot=ballot, video_id=letter * 11,
        **({'title': 'Rozmowa z Janem Nowakiem', 'channel': 'Kanał', 'duration': 480,
            'guest_name': 'Jan Nowak', 'guest_keys': ['nowak'], 'views': 100, 'score': 100} | fields))


def client(user=None):
    result = APIClient()
    if user:
        result.force_authenticate(user)
    return result


def close(monkeypatch):
    monkeypatch.setattr(timezone, 'now', lambda: votes.closing_at(DAY))


def test_interview_add_valid_duplicate_merge_and_limit(users, monkeypatch):
    api = yt(monkeypatch)
    first = votes.add_candidate(users[0], DAY, 'https://youtu.be/' + 'a' * 11)
    assert first.duration == 480 and first.guest_name == 'Jan Nowak'
    assert votes.add_candidate(users[0], DAY, 'https://www.youtube.com/watch?v=' + 'a' * 11).pk == first.pk
    assert votes.add_candidate(users[1], DAY, 'https://youtu.be/' + 'a' * 11).pk == first.pk
    assert api.call_count == 1
    for letter in 'bc':
        votes.add_candidate(users[0], DAY, 'https://youtu.be/' + letter * 11)
    with pytest.raises(ValidationError, match='3 wywiady'):
        votes.add_candidate(users[0], DAY, 'https://youtu.be/' + 'd' * 11)
    assert api.call_count == 3  # quota checked before YouTube
    assert InterviewCandidate.objects.count() == 3
    assert InterviewSubmission.objects.filter(user=users[0]).count() == 3
    assert votes.add_candidate(users[0], DAY, 'https://youtu.be/' + 'a' * 11).pk == first.pk


@pytest.mark.parametrize('link', ['https://evil.test/youtube.com/watch?v=aaaaaaaaaaa',
    'https://youtube.com.evil.test/watch?v=aaaaaaaaaaa', 'https://youtu.be/short', 'javascript:aaaaaaaaaaa'])
def test_interview_add_invalid_url(users, monkeypatch, link):
    api = yt(monkeypatch)
    with pytest.raises(ValidationError, match='poprawny link'):
        votes.add_candidate(users[0], DAY, link)
    api.assert_not_called()


@pytest.mark.parametrize('items,reason', [
    ([], 'nie istnieje'),
    ([video(snippet={'publishedAt': '2026-10-02T22:00:00Z'})], 'wybranym dniu'),
    ([video(snippet={'publishedAt': '2026-10-01T21:59:59Z'})], 'wybranym dniu'),
    ([video(contentDetails={'duration': 'PT7M59S'})], '8 minut'),
    ([video(snippet={'title': 'Rozmowa z Janem Nieznanym'})], 'z politykiem'),
    ([video(snippet={'title': 'Komentarz Jana Nowaka'})], 'z politykiem'),
])
def test_interview_add_validation(users, monkeypatch, items, reason):
    yt(monkeypatch, items)
    with pytest.raises(ValidationError, match=reason):
        votes.add_candidate(users[0], DAY, 'https://youtu.be/aaaaaaaaaaa')
    assert not InterviewCandidate.objects.exists()


def test_interview_add_warsaw_midnight_description_and_no_paid_models(users, monkeypatch):
    yt(monkeypatch, [video(snippet={'publishedAt': '2026-10-01T22:00:00Z', 'title': 'Poranny program',
                                 'description': 'Rozmowa z Janem Nowakiem'})])
    monkeypatch.setattr(interviews, 'looks_like_interview', Mock(side_effect=AssertionError('Bez modeli')))
    monkeypatch.setattr(interviews.clinic_ai, '_free_chat', Mock(side_effect=AssertionError('Bez modeli')))
    assert votes.add_candidate(users[0], DAY, 'https://youtu.be/aaaaaaaaaaa').guest_name == 'Jan Nowak'


def test_interview_add_upstream_failure_is_polish_and_does_not_use_slot(users, monkeypatch):
    monkeypatch.setattr(interviews, '_yt', Mock(side_effect=interviews.clinic_ai.ClinicAIError('youtube_quota')))
    with pytest.raises(ValidationError, match='Spróbuj później'):
        votes.add_candidate(users[0], DAY, 'https://youtu.be/aaaaaaaaaaa')
    assert InterviewSubmission.objects.count() == 0


def test_interview_vote_one_per_day_change_and_own_candidate(users, monkeypatch):
    yt(monkeypatch)
    a = votes.add_candidate(users[0], DAY, 'https://youtu.be/aaaaaaaaaaa')
    b = candidate('b')
    votes.cast_vote(users[0], DAY, a.pk)
    votes.cast_vote(users[0], DAY, a.pk)
    votes.cast_vote(users[0], DAY, b.pk)
    assert InterviewVote.objects.count() == 1
    assert InterviewVote.objects.get().candidate_id == b.pk
    today = candidate('c', NOW.date())
    votes.cast_vote(users[0], NOW.date(), today.pk)
    assert InterviewVote.objects.count() == 2
    with pytest.raises(ValidationError, match='takiego kandydata'):
        votes.cast_vote(users[1], DAY, today.pk)
    with pytest.raises(IntegrityError), transaction.atomic():
        InterviewVote.objects.create(user=users[0], ballot=b.ballot, candidate=a)


@pytest.mark.parametrize('offset,allowed', [(-1, True), (0, False), (1, False)])
def test_interview_vote_and_add_close_at_seven(users, monkeypatch, offset, allowed):
    row = candidate()
    monkeypatch.setattr(timezone, 'now', lambda: votes.closing_at(DAY) + timedelta(microseconds=offset))
    for action in [lambda: votes.cast_vote(users[0], DAY, row.pk),
                   lambda: votes.add_candidate(users[0], DAY, 'https://youtu.be/aaaaaaaaaaa')]:
        if allowed:
            action()
        else:
            with pytest.raises(ValidationError, match='7:00'):
                action()


def test_interview_add_rechecks_closing_after_youtube(users, monkeypatch):
    def fetch(*args, **kwargs):
        close(monkeypatch)
        return {'items': [video()]}
    monkeypatch.setattr(interviews, '_yt', fetch)
    with pytest.raises(ValidationError, match='7:00'):
        votes.add_candidate(users[0], DAY, 'https://youtu.be/aaaaaaaaaaa')
    assert not InterviewSubmission.objects.exists()


def test_interview_vote_verified_and_enabled(users, settings):
    row = candidate()
    AccountIdentity.objects.filter(user=users[0]).update(email_verified=False)
    for user in users[:2]:
        if user == users[1]:
            settings.ACCOUNTS_ENABLED = False
        with pytest.raises(PermissionDenied):
            votes.cast_vote(user, DAY, row.pk)
        with pytest.raises(PermissionDenied):
            votes.add_candidate(user, DAY, 'https://youtu.be/aaaaaaaaaaa')


@pytest.mark.parametrize('counts,expected,method', [((2, 1), 'a', 'votes'), ((1, 1), 'b', 'tie'), ((0, 0), 'b', 'views')])
def test_interview_selection_votes_tie_no_votes(users, monkeypatch, counts, expected, method):
    monkeypatch.setenv('INTERVIEW_READER_PICK', 'false')
    a, b = candidate('a', score=10), candidate('b', score=1000)
    index = 0
    for row, count in zip((a, b), counts):
        for _ in range(count):
            votes.cast_vote(users[index], DAY, row.pk)
            index += 1
    assert interviews.pick_yesterday()['status'] == 'voting_open'
    close(monkeypatch)
    result = interviews.pick_yesterday()
    chosen = ClinicInterview.objects.get(pk=result['id'])
    assert chosen.video_id == expected * 11 and chosen.selection_method == method
    assert chosen.selection_votes == max(counts)
    assert votes.selection_label(chosen) == interviews.interview_data(chosen)['selection_label']
    assert interviews.pick_yesterday()['status'] == 'already_chosen'


def test_interview_selection_skips_same_guest_two_days(users, monkeypatch):
    monkeypatch.setenv('INTERVIEW_READER_PICK', 'false')
    a = candidate('a', score=1000)
    b = candidate('b', score=10, guest_keys=['kowalsk'], guest_name='Anna Kowalska')
    ClinicInterview.objects.create(day=DAY - timedelta(days=1), video_id='z' * 11,
                                  guest_name='Jan Nowak', status='approved')
    votes.cast_vote(users[0], DAY, a.pk)
    votes.cast_vote(users[1], DAY, a.pk)
    votes.cast_vote(users[2], DAY, b.pk)
    close(monkeypatch)
    assert interviews.pick_yesterday()['id'] == ClinicInterview.objects.get(video_id=b.video_id).pk


def test_interview_rescuer_uses_next_voted_candidate(users, monkeypatch):
    monkeypatch.setenv('INTERVIEW_READER_PICK', 'false')
    a, b = candidate('a'), candidate('b', guest_keys=['kowalsk'])
    votes.cast_vote(users[0], DAY, a.pk)
    votes.cast_vote(users[1], DAY, a.pk)
    votes.cast_vote(users[2], DAY, b.pk)
    close(monkeypatch)
    first = interviews.pick_yesterday()
    ClinicInterview.objects.filter(pk=first['id']).update(status='failed', error='timeout')
    assert interviews.pick_yesterday()['status'] == 'requeued'
    ClinicInterview.objects.filter(pk=first['id']).update(status='failed', error='timeout')
    assert interviews.pick_yesterday(next_candidate=True)['id'] == ClinicInterview.objects.get(video_id=b.video_id).pk


def test_interview_never_reuses_video_from_another_day(users, monkeypatch):
    monkeypatch.setenv('INTERVIEW_READER_PICK', 'false')
    a, b = candidate('a'), candidate('b')
    older = ClinicInterview.objects.create(day=DAY - timedelta(days=3), video_id=a.video_id, status='approved')
    votes.cast_vote(users[0], DAY, a.pk)
    close(monkeypatch)
    interviews.pick_yesterday()
    older.refresh_from_db()
    assert older.day == DAY - timedelta(days=3)
    assert ClinicInterview.objects.get(day=DAY).video_id == b.video_id


def test_interview_candidate_task_scans_today_or_yesterday(monkeypatch):
    from news.tasks import clinic_interview_candidates_task
    monkeypatch.setenv('CLINIC_INTERVIEW_ENABLED', 'true')
    refresh = Mock(return_value=2)
    monkeypatch.setattr(votes, 'refresh_candidates', refresh)
    assert clinic_interview_candidates_task()['day'] == str(DAY)
    refresh.assert_called_with(DAY)
    monkeypatch.setattr(timezone, 'now', lambda: NOW.replace(hour=18))
    assert clinic_interview_candidates_task()['day'] == str(NOW.date())
    refresh.assert_called_with(NOW.date())


def test_interview_candidates_refresh_union_freeze_and_public_read_no_api(users, monkeypatch, settings):
    added = candidate('a')
    ranking = Mock(return_value=[{'video_id': 'b' * 11, 'title': 'Rozmowa z Anną Kowalską', 'views': 800, 'score': 800}])
    monkeypatch.setattr(interviews, 'rank_interviews', ranking)
    assert votes.refresh_candidates(DAY) == 2
    assert votes.refresh_candidates(DAY) == 2
    close(monkeypatch)
    assert votes.refresh_candidates(DAY) == 0
    assert ranking.call_count == 2
    settings.ACCOUNTS_ENABLED = False
    data = client().get(URL).data
    assert len(data['results']) == 2 and data['accounts_enabled'] is False
    assert data['results'][0]['views'] == 800
    assert ranking.call_count == 2
    assert InterviewCandidate.objects.filter(pk=added.pk).exists()


def test_interview_vote_api_auth_validation_privacy_and_change(users, monkeypatch, settings):
    api = yt(monkeypatch)
    a, b = candidate('a'), candidate('b', views=999)
    for suffix, payload in [('', {'url': 'https://youtu.be/aaaaaaaaaaa'}), ('vote/', {'candidate_id': a.pk})]:
        assert client().post(URL + suffix, payload).status_code in (401, 403)
        AccountIdentity.objects.filter(user=users[0]).update(email_verified=False)
        assert client(users[0]).post(URL + suffix, payload).status_code == 403
        settings.ACCOUNTS_ENABLED = False
        assert client(users[1]).post(URL + suffix, payload).status_code == 404
        settings.ACCOUNTS_ENABLED = True
    reader = client(users[1])
    assert reader.post(URL, {'url': 'https://youtu.be/aaaaaaaaaaa'}).status_code == 200
    assert reader.post(URL + 'vote/', {'candidate_id': a.pk}).data['mine'] == a.pk
    public = client().get(URL)
    assert public.data['mine'] is None
    assert public['Cache-Control'] == 'private, no-store'
    assert public.data['results'][0]['id'] == a.pk
    assert public.data['results'][0]['votes'] == 1
    assert not {'user', 'email', 'ip', 'submissions'} & set(public.data['results'][0])
    assert reader.post(URL + 'vote/', {'candidate_id': b.pk}).data['mine'] == b.pk
    assert reader.post(URL + 'vote/', {'candidate_id': 'bad'}).status_code == 400
    assert client().get(URL, {'day': 'bad'}).status_code == 400
    close(monkeypatch)
    assert reader.post(URL + 'vote/', {'candidate_id': a.pk}).status_code == 400
    assert reader.post(URL, {'url': 'https://youtu.be/aaaaaaaaaaa'}).status_code == 400
    api.assert_not_called()


@pytest.mark.parametrize('suffix,payload,limit', [('', {'url': 'bad'}, 10), ('vote/', {'candidate_id': 999}, 30)])
def test_interview_api_rate_limits(users, suffix, payload, limit):
    reader = client(users[0])
    for _ in range(limit):
        assert reader.post(URL + suffix, payload).status_code == 400
    assert reader.post(URL + suffix, payload).status_code == 429


@pytest.mark.parametrize('day', [date(2026, 3, 28), date(2026, 10, 24)])
def test_interview_closing_uses_warsaw_across_dst(day):
    assert votes.closing_at(day).astimezone(WARSAW).hour == 7
    assert votes.closing_at(day).date() == day + timedelta(days=1)


def test_interview_schedule_keeps_milestone_and_populates_before_close():
    assert BEAT_PLAN['clinic-interview-pick'][1] == {'hour': '7,10,13,16,19', 'minute': 5}
    assert '6' in BEAT_PLAN['clinic-interview-candidates'][1]['hour'].split(',')
    assert next(row for row in MILESTONES if row.key == 'interview').deadline == 'wybór 8:00, gotowy 18:00'


def test_two_interviews_dr_spin_by_ranking_and_readers_by_votes(users, monkeypatch):
    """Właściciel 4.10: pierwszy wywiad wybiera Dr. Spin (ranking), drugi czytelnicy (głosy, min. 3)."""
    monkeypatch.setenv('INTERVIEW_READER_PICK', 'true')
    monkeypatch.setenv('INTERVIEW_READER_MIN_VOTES', '3')
    loud, voted = candidate('a', score=1000, from_ranking=True), candidate('b', score=10, guest_keys=['kowalsk'], guest_name='Anna Kowalska')
    for i in range(3):
        votes.cast_vote(users[i], DAY, voted.pk)
    close(monkeypatch)
    result = interviews.pick_yesterday()
    assert result['status'] == 'queued' and len(result['ids']) == 2
    auto = ClinicInterview.objects.get(day=DAY, video_id=loud.video_id)
    readers = ClinicInterview.objects.get(day=DAY, video_id=voted.video_id)
    assert auto.selection_method == 'views' and readers.selection_method == 'votes' and readers.selection_votes == 3
    assert 'czytelników' in votes.selection_label(readers) and 'Dr. Spina' in votes.selection_label(auto)
    assert interviews.pick_yesterday()['status'] == 'already_chosen'


def test_reader_pick_needs_minimum_votes(users, monkeypatch):
    monkeypatch.setenv('INTERVIEW_READER_PICK', 'true')
    monkeypatch.setenv('INTERVIEW_READER_MIN_VOTES', '3')
    candidate('a', score=1000, from_ranking=True)
    voted = candidate('b', score=10, guest_keys=['kowalsk'], guest_name='Anna Kowalska')
    votes.cast_vote(users[0], DAY, voted.pk)
    close(monkeypatch)
    result = interviews.pick_yesterday()
    assert len(result['ids']) == 1 and not ClinicInterview.objects.filter(day=DAY, video_id=voted.video_id).exists()


def test_reader_pick_skips_guest_already_chosen_by_dr_spin(users, monkeypatch):
    monkeypatch.setenv('INTERVIEW_READER_PICK', 'true')
    monkeypatch.setenv('INTERVIEW_READER_MIN_VOTES', '1')
    candidate('a', score=1000, from_ranking=True)
    same = candidate('b', score=10)
    votes.cast_vote(users[0], DAY, same.pk)
    close(monkeypatch)
    assert len(interviews.pick_yesterday()['ids']) == 1


def test_message_to_dr_spin_limit_and_ballot_fields(users, monkeypatch):
    monkeypatch.setenv('INTERVIEW_READER_PICK', 'true')
    candidate('a')
    api = client(users[0])
    for i in range(3):
        response = api.post('/api/clinic/interviews/voting/message/', {'day': DAY.isoformat(), 'text': f'Proszę o wywiad z ministrem nr {i}'}, format='json')
        assert response.status_code == 200 and response.data['sent']
    assert response.data['messages_left'] == 0 and response.data['min_votes'] == 3 and response.data['dr_spin'] is None
    assert api.post('/api/clinic/interviews/voting/message/', {'day': DAY.isoformat(), 'text': 'Jeszcze jedna wiadomość'}, format='json').status_code == 400
    assert client().post('/api/clinic/interviews/voting/message/', {'text': 'Bez konta nie wolno'}, format='json').status_code in (401, 403)


def test_vote_needs_account_age(users, monkeypatch):
    monkeypatch.setenv('INTERVIEW_MIN_ACCOUNT_DAYS', '3')
    row = candidate('a')
    users[0].date_joined = NOW
    users[0].save(update_fields=['date_joined'])
    with pytest.raises(PermissionDenied, match='3 dniach'):
        votes.cast_vote(users[0], DAY, row.pk)
    users[1].date_joined = NOW - timedelta(days=4)
    users[1].save(update_fields=['date_joined'])
    votes.cast_vote(users[1], DAY, row.pk)
