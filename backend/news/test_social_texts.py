import pytest
from django.core.management import call_command
from django.utils import timezone

from news import clinic_ai, social_publish, x_publish
from news.clinic_models import SpinDiagnosis
from news.names import display_name
from news.social_content import checked_claims
from news.test_clinic import account, post
from news.x_share import build, shorten, weight


def sample():
    return {
        'id': 7007, 'author': {'name': 'Anna KOWALSKA-NOWAK', 'party': {'short': 'Partia A'}},
        'verdict_label': 'Spin', 'intensity': 70,
        'techniques': [{'name': 'Selekcja danych'}],
        'x_thread': ['Wpis pomija okres porównania.', 'Dane urzędu pokazują spadek także w poprzednim roku.',
                     'Selekcja danych zawęża obraz zmiany.'],
        'claims': [{'claim': 'Spadek nastąpił dopiero teraz.', 'assessment': 'misleading',
                    'explanation': 'Spadek zaczął się wcześniej.',
                    'sources': [{'url': 'https://example.org/dane', 'title': 'Dane urzędu'}]}],
    }


@pytest.mark.parametrize('raw, expected', [
    ('Ewa ZAJĄCZKOWSKA-HERNIK', 'Ewa Zajączkowska-Hernik'),
    ('Ewa Zajączkowska-HERNIK', 'Ewa Zajączkowska-Hernik'),
    ('Konfederacja', 'Konfederacja'), ('Polska 2050', 'Polska 2050'), ('PSL', 'PSL'),
])
def test_names(raw, expected):
    assert display_name(raw) == expected


def test_complete_sentences_and_channel_formats():
    data = sample()
    posts = build(data, account=True)
    assert len(posts) == 2 and all(weight(text) <= 280 for text in posts)
    assert 'http' not in posts[0] and 'Techniki: selekcja danych.' in posts[0]
    assert 'Źródło: https://example.org/dane' in posts[1]
    assert len(build(data)) == 1
    captions = social_publish.texts_from_data(data)
    assert all(point in captions['facebook'] for point in data['x_thread'])
    assert captions['facebook'].endswith(social_publish.FOOTER)
    assert len(captions['bluesky']) <= 300
    assert '…' not in ''.join(posts + list(captions.values()))
    assert shorten('To jest bardzo długie zdanie.', 10) == ''
    data['x_thread'][0] = 'Słowo ' * 100 + '.'
    assert build(data, account=True) == []


@pytest.mark.parametrize('lead', ['Czy to prawda?', 'To manipulacja!', 'Wpis pomija kontekst. #spin', 'Wpis pomija kontekst. 🔥'])
def test_unprofessional_cached_synthesis_is_not_published(lead):
    data = sample()
    data['x_thread'][0] = lead
    assert build(data, account=True) == []
    data['x_thread'] = []
    assert build(data, account=True) == []


def test_only_sourced_claims_reach_ai_and_video(monkeypatch):
    from news import social_video
    from news.clinic_council import UNCHECKED
    data = sample()
    bad = {'claim': 'NIESPRAWDZONA TEZA', 'assessment': 'unverified', 'explanation': UNCHECKED, 'sources': []}
    data['claims'].append(bad)
    assert len(checked_claims(data['claims'])) == 1
    assert 'NIESPRAWDZONA TEZA' not in clinic_ai._x_thread_input(data)
    assert UNCHECKED not in clinic_ai._x_thread_input(data)
    labels = []
    original = social_video._chrome
    monkeypatch.setattr(social_video, '_chrome', lambda scene, label: (labels.append(label), original(scene, label)))
    data['claims'] = [bad]
    scenes = social_video.build_scenes(data, {'name': 'Ewa ZAJĄCZKOWSKA-HERNIK', 'text': 'Pełne zdanie.'})
    assert scenes[0].duration == 2.6
    assert not any('Terapia' in label or 'Źródła' in label for label in labels)
    bad['assessment'] = 'supported'
    bad['sources'] = [{'url': 'https://example.org'}]
    assert checked_claims([bad]) == []


@pytest.mark.django_db
def test_balanced_candidates_and_zero_limit():
    from news.clinic_models import SocialPost
    gov = account(camp='government', handle='gov', user_id='301')
    opp = account(camp='opposition', handle='opp', user_id='302')
    def make(acc, pk, strength):
        return SpinDiagnosis.objects.create(post=post(acc, post_id=str(pk)), status='approved', verdict='spin',
                                            intensity=strength, diagnosed_at=timezone.now())
    strongest = make(gov, 1, 95)
    make(gov, 2, 90)
    other = make(opp, 3, 56)
    assert x_publish.candidates(2) == [strongest, other]
    assert social_publish.candidates(2, ['facebook']) == [strongest, other]
    assert x_publish.candidates(0) == social_publish.candidates(0, ['facebook']) == []
    strongest.x_posted_at = timezone.now()
    strongest.save(update_fields=['x_posted_at'])
    SocialPost.objects.create(diagnosis=strongest, platform='facebook')
    assert x_publish.candidates(1) == [other]
    assert social_publish.candidates(1, ['facebook']) == [other]
    other.intensity = 54
    other.save(update_fields=['intensity'])
    assert x_publish.candidates(2) == social_publish.candidates(2, ['facebook']) == []


@pytest.mark.django_db
def test_preview_missing_synthesis_does_not_write(monkeypatch, tmp_path):
    row = SpinDiagnosis.objects.create(post=post(account()), verdict='spin', intensity=70,
                                       status='approved', diagnosed_at=timezone.now())
    monkeypatch.setattr(clinic_ai, 'x_thread', lambda data: {'posts': sample()['x_thread']})
    monkeypatch.setattr(x_publish, 'polish', lambda text: text)
    monkeypatch.setattr('news.clinic.polish_synthesis', lambda posts: posts)  # językoznawca Konsylium: bez zapytań do modeli
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as queries:
        call_command('social_preview', row.pk, out=str(tmp_path))
    assert not any(q['sql'].lstrip().split()[0].upper() in ('INSERT', 'UPDATE', 'DELETE') for q in queries)
    row.refresh_from_db()
    assert row.x_thread == [] and row.x_posted_ids == [] and row.x_posted_at is None
    assert (tmp_path / 'karta.png').read_bytes().startswith(b'\x89PNG')
    assert 'Wpis 2' in (tmp_path / 'wpisy.txt').read_text(encoding='utf-8')


@pytest.mark.django_db
def test_missing_synthesis_blocks_publication(monkeypatch):
    row = SpinDiagnosis.objects.create(post=post(account()), verdict='spin', intensity=70,
                                       status='approved', diagnosed_at=timezone.now())
    monkeypatch.setattr(x_publish, 'enabled', lambda: True)
    def unavailable(data):
        raise clinic_ai.ClinicAIError('unavailable')
    monkeypatch.setattr(clinic_ai, 'x_thread', unavailable)
    monkeypatch.setattr(x_publish, 'post', lambda *args, **kwargs: pytest.fail('Nie wolno publikować.'))
    assert x_publish.run()['results'][0]['error'] == 'synthesis_unavailable'
    row.refresh_from_db()
    assert row.x_posted_ids == []


@pytest.mark.django_db
def test_partial_thread_is_saved_and_reply_can_resume(monkeypatch):
    row = SpinDiagnosis.objects.create(post=post(account()), verdict='spin', intensity=70,
                                       status='approved', diagnosed_at=timezone.now(), x_thread=sample()['x_thread'])
    monkeypatch.setattr(x_publish, 'enabled', lambda: True)
    monkeypatch.setattr(x_publish, 'polish', lambda text: text)
    monkeypatch.setattr(x_publish, 'upload_image', lambda png: 'image')
    monkeypatch.setattr(x_publish, 'alert', lambda *args: None)
    calls = []
    def fail_reply(text, reply_to=None, media_id=None):
        calls.append((reply_to, media_id))
        if reply_to:
            raise RuntimeError('reply_failed')
        return 'first'
    monkeypatch.setattr(x_publish, 'post', fail_reply)
    assert x_publish.run()['results'][0]['posted'] is False
    row.refresh_from_db()
    assert row.x_posted_ids == ['first'] and row.x_posted_at is None
    def reply(text, reply_to=None, media_id=None):
        assert reply_to == 'first' and media_id is None
        return 'second'
    monkeypatch.setattr(x_publish, 'post', reply)
    assert x_publish.run()['results'][0]['posted'] is True
    row.refresh_from_db()
    assert row.x_posted_ids == ['first', 'second']


@pytest.mark.django_db
def test_preview_video_and_unavailable_synthesis(monkeypatch, tmp_path):
    row = SpinDiagnosis.objects.create(post=post(account()), verdict='spin', intensity=70)
    def unavailable(data):
        raise clinic_ai.ClinicAIError('unavailable')
    monkeypatch.setattr(clinic_ai, 'x_thread', unavailable)
    calls = []
    monkeypatch.setattr('news.social_video.render', lambda data, card, path: calls.append(path))
    call_command('social_preview', row.pk, out=str(tmp_path), video=True)
    assert calls == [str(tmp_path / 'film.mp4')]
    assert 'publikacja zostanie pominięta' in (tmp_path / 'wpisy.txt').read_text(encoding='utf-8')
    row.refresh_from_db()
    assert row.x_thread == []


def test_polish_rejects_changed_numbers_and_truncation(monkeypatch):
    original = build(sample(), account=True)[0]
    for fixed in [original.replace('70/100', '90/100'), original + '…']:
        monkeypatch.setattr(clinic_ai, '_free_chat', lambda *args, **kwargs: ({'text': fixed}, 'test'))
        assert x_publish.polish(original) == original


def test_source_matches_the_named_claim_when_there_are_several():
    data = sample()
    data['claims'].insert(0, {'assessment': 'supported', 'explanation': 'Inna kwestia.',
                               'sources': [{'url': 'https://example.org/inne', 'title': 'Inny raport'}]})
    second = build(data, account=True)[1]
    assert 'Źródło: https://example.org/dane' in second and '/inne' not in second


def test_bluesky_removes_whole_sentences():
    body = 'Nagłówek\n' + 'Zdanie zawiera wyjaśnienie. ' * 15
    result = social_publish._bluesky_text(body, 'https://example.org/diagnoza')
    assert len(result) <= 300 and '…' not in result
    assert result.split('\n\n')[0].endswith('.')


def test_alternation_continues_from_previous_day():
    from datetime import timedelta
    from types import SimpleNamespace
    from news.social_selection import select
    rows = [SimpleNamespace(post=SimpleNamespace(camp_at_collection=camp))
            for camp in ('government', 'opposition')]
    assert select(rows, [('government', timezone.now() - timedelta(days=1))], 1) == [rows[1]]
