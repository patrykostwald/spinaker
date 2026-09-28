from types import SimpleNamespace

import pytest
from django.utils import timezone

from news import social_publish
from news.clinic_models import SocialPost, SpinDiagnosis
from news.test_clinic import account, post


def test_bluesky_link_facets_count_bytes_not_characters():
    text = 'Żółć — spin 82/100\n\nhttps://spin.clinic/klinika/7'
    facet = social_publish.link_facets(text)[0]
    raw = text.encode('utf-8')
    assert raw[facet['index']['byteStart']:facet['index']['byteEnd']] == b'https://spin.clinic/klinika/7'
    long = social_publish._bluesky_text('słowo ' * 80, 'https://spin.clinic/klinika/7')
    assert len(long) <= 300 and long.endswith('https://spin.clinic/klinika/7')


def test_channels_need_switch_and_keys(monkeypatch):
    monkeypatch.setenv('BLUESKY_HANDLE', 'spinclinic.bsky.social')
    monkeypatch.setenv('BLUESKY_APP_PASSWORD', 'abcd-efgh-ijkl-mnop')
    monkeypatch.delenv('SOCIAL_VIDEO_EMAIL', raising=False)
    monkeypatch.delenv('X_POST_ALERT_EMAIL', raising=False)
    assert social_publish.channels() == []  # bez SOCIAL_POST_ENABLED nic nie idzie
    monkeypatch.setenv('SOCIAL_POST_ENABLED', 'true')
    assert social_publish.channels() == ['bluesky']


def test_video_name_is_not_guessable(settings):
    name = social_publish.video_name(12)
    assert social_publish.VIDEO_NAME.match(name) and name != social_publish.video_name(13)
    settings.SECRET_KEY = 'inny-klucz'
    assert social_publish.video_name(12) != name


@pytest.mark.django_db
def test_bluesky_post_once_and_removed_when_author_deletes(monkeypatch):
    acc = account()
    row = SpinDiagnosis.objects.create(post=post(acc), status='approved', verdict='spin', intensity=85, headline='Teza bez dowodu',
                                       summary='Krótko.', x_thread=['Wpis pomija kontekst.', 'Autor stosuje fałszywą alternatywę.'], techniques=[{'name': 'Fałszywa alternatywa', 'quote': 'Tylko my', 'explanation': '…'}],
                                       diagnosed_at=timezone.now())
    monkeypatch.setenv('SOCIAL_POST_ENABLED', 'true')
    monkeypatch.setenv('BLUESKY_HANDLE', 'spinclinic.bsky.social')
    monkeypatch.setenv('BLUESKY_APP_PASSWORD', 'abcd-efgh-ijkl-mnop')
    monkeypatch.delenv('SOCIAL_VIDEO_EMAIL', raising=False)
    monkeypatch.delenv('X_POST_ALERT_EMAIL', raising=False)
    monkeypatch.setattr('news.x_publish.polish', lambda text: text)
    calls = []

    def fake_post(url, timeout, json=None, data=None, headers=None):
        calls.append(url.rsplit('/', 1)[-1])
        if url.endswith('createSession'):
            return SimpleNamespace(status_code=200, json=lambda: {'accessJwt': 'jwt', 'did': 'did:plc:x', 'handle': 'spinclinic.bsky.social'})
        if url.endswith('uploadBlob'):
            assert data[:4] == bytes([0x89]) + b'PNG'  # karta PNG z wpisem polityka
            return SimpleNamespace(status_code=200, json=lambda: {'blob': {'ref': 'b'}})
        if url.endswith('createRecord'):
            record = json['record']
            assert len(record['text']) <= 300 and '@posel_test' not in record['text'] and 'x.com/' not in record['text']
            assert record['facets'] and record['text'].endswith(f'/klinika/{row.pk}')
            return SimpleNamespace(status_code=200, json=lambda: {'uri': 'at://did:plc:x/app.bsky.feed.post/abc'})
        if url.endswith('deleteRecord'):
            assert json['rkey'] == 'abc'
            return SimpleNamespace(status_code=200, json=lambda: {})
        raise AssertionError(url)

    monkeypatch.setattr(social_publish.requests, 'post', fake_post)
    result = social_publish.run()
    assert result['results'] == [{'id': row.pk, 'platform': 'bluesky', 'posted': True}]
    item = SocialPost.objects.get(diagnosis=row)
    assert item.url == 'https://bsky.app/profile/spinclinic.bsky.social/post/abc'
    assert social_publish.run()['results'] == []  # ta sama diagnoza nie idzie drugi raz

    from news import deleted_posts
    deleted_posts.mark_deleted(row.post)
    item.refresh_from_db()
    assert calls[-1].endswith('deleteRecord') and item.deleted_at is not None


@pytest.mark.django_db
def test_second_interview_of_the_day_sits_under_the_automatic_one():
    from datetime import timedelta
    from news import clinic_interview
    from news.clinic_models import ClinicInterview
    now = timezone.now()

    def make(vid, day, hours_ago):
        return ClinicInterview.objects.create(video_id=vid, url=f'https://www.youtube.com/watch?v={vid}', day=day,
                                              status='approved', headline=vid, diagnosed_at=now - timedelta(hours=hours_ago))
    today = timezone.localdate()
    old = make('AAAAAAAAAA1', today - timedelta(days=2), 30)       # wczorajsze wydanie → archiwum
    auto = make('AAAAAAAAAA2', today - timedelta(days=1), 2)       # automat rano: rozmowa z wczoraj
    manual = make('AAAAAAAAAA3', today, 0)                          # dodany ręcznie: dzisiejsza rozmowa
    if timezone.localdate(auto.diagnosed_at) != timezone.localdate(manual.diagnosed_at):
        pytest.skip('test uruchomiony tuż po północy')
    assert clinic_interview.latest_interview_data()['id'] == auto.pk
    assert clinic_interview.second_interview_data()['id'] == manual.pk
    assert [row['id'] for row in clinic_interview.interview_archive()] == [old.pk]


@pytest.mark.django_db
def test_spin_of_day_per_camp_puts_stronger_fresh_spin_first():
    from datetime import timedelta
    from news import clinic
    gov, opp = account(camp='government', handle='rzad_test', user_id='301'), account(camp='opposition', handle='opoz_test', user_id='302')
    make = lambda acc, pid, intensity, hours: SpinDiagnosis.objects.create(
        post=post(acc, post_id=pid, hours_ago=hours), status='approved', verdict='spin', intensity=intensity,
        headline=f'h{pid}', summary='s', diagnosed_at=timezone.now())
    make(gov, '7001', 60, 1)
    make(opp, '7002', 85, 1)
    make(opp, '7003', 95, 200)  # mocniejszy, ale sprzed ponad trzech dni — nie wygrywa ze świeżym
    data = clinic.spin_of_day_by_camp()
    assert data['order'] == ['opposition', 'government']
    assert data['spins']['opposition']['intensity'] == 85 and data['spins']['government']['intensity'] == 60
    SpinDiagnosis.objects.filter(post__post_id='7002').delete()
    data = clinic.spin_of_day_by_camp()
    assert data['spins']['opposition']['window'] == 'latest' and data['order'][0] == 'government'


def test_tool_failure_text_is_not_shown_as_claim_explanation():
    from news.clinic_council import check_failed, clean_claim
    leaked = {'claim': 'X', 'assessment': 'unverified', 'sources': [],
              'explanation': 'Nie udało się przeprowadzić weryfikacji w wyszukiwarce z powodu wyczerpania limitu zapytań narzędzia wyszukiwania w tej sesji.'}
    cleaned = clean_claim(leaked)
    assert cleaned['explanation'].startswith('Nie sprawdzono w wyszukiwarce') and cleaned['assessment'] == 'unverified'
    real = {'claim': 'Y', 'assessment': 'contradicted', 'explanation': 'GUS podaje inną liczbę.', 'sources': [{'url': 'https://stat.gov.pl', 'title': 'GUS'}]}
    assert clean_claim(real) == real
    assert check_failed([cleaned, cleaned]) and not check_failed([cleaned, real])
