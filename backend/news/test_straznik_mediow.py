"""Strażnik mediów i „Tę tezę sprawdzili” (raport źródeł 6.10). Bez sieci: zapytania podmienione."""
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from news import fakty, straznik_mediow as sm
from news.clinic_models import SpinDiagnosis
from news.zrodla_models import CitedArticle

pytestmark = pytest.mark.django_db
URL = 'https://www.example-news.pl/kraj/artykul-1'
PAGE = ('<html><head><title>Tytuł artykułu</title></head><body><nav><p>Menu menu menu menu menu menu menu menu menu</p></nav>'
        '<article><p>Pierwszy akapit artykułu, który ma odpowiednią długość do liczenia.</p>'
        '<p>Drugi akapit artykułu z liczbą 1000 zł i cytatem polityka.</p></article></body></html>')


def published(claims, **extra):
    from news.test_clinic import account, post
    return SpinDiagnosis.objects.create(post=post(account()), status='approved', diagnosed_at=timezone.now(), claims=claims,
                                        headline='Nagłówek', verdict='spin', intensity=50, **extra)


def response(code=200, body=PAGE, headers=None, json_data=None):
    r = Mock(status_code=code, headers=headers or {}, text=body if isinstance(body, str) else '')
    r.raw.read.return_value = body.encode() if isinstance(body, str) else body
    r.json.return_value = json_data
    r.raise_for_status = Mock()
    return r


def test_cited_urls_from_published_diagnoses_skip_x_and_factchecks():
    published([{'claim': 'Teza', 'sources': [{'url': URL}, {'url': 'https://x.com/a/status/1'},
                                              {'url': 'https://demagog.org.pl/a', 'type': 'istniejący fact-check'}]}])
    found = sm.cited_urls()
    assert list(found) == [URL]
    assert sm.register() == 1 and sm.register() == 0
    assert CitedArticle.objects.get().cited_by[0].startswith('diagnosis:')


def test_fingerprint_ignores_navigation_and_keeps_no_text():
    title, digest = sm.fingerprint(PAGE.encode())
    assert title == 'Tytuł artykułu' and len(digest) == 64
    changed = PAGE.replace('1000 zł', '2000 zł')
    assert sm.fingerprint(changed.encode())[1] != digest
    assert sm.fingerprint(PAGE.replace('Menu menu', 'Inne menu').encode())[1] == digest


def test_run_archives_then_detects_silent_edit(monkeypatch):
    monkeypatch.setenv('MEDIA_WATCH_ENABLED', 'true')
    monkeypatch.delenv('IA_S3_ACCESS', raising=False)
    published([{'claim': 'Teza', 'sources': [{'url': URL}]}])
    stamp = timezone.now().strftime('%Y%m%d%H%M%S')
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if url == sm.AVAILABLE:
            return response(json_data={'archived_snapshots': {}})
        if url.startswith(sm.SAVE):
            return response(302, headers={'Location': f'https://web.archive.org/web/{stamp}/{URL}'})
        if url.endswith('/robots.txt'):
            return response(200, 'User-agent: *\nAllow: /')
        return response(200, fake_get.page)
    fake_get.page = PAGE
    with patch.object(sm, '_get', side_effect=fake_get):
        first = sm.run()
    row = CitedArticle.objects.get()
    assert first['archived'] == 1 and row.archive_url == f'https://web.archive.org/web/{stamp}/{URL}'
    assert row.first_sha256 and row.check_status == 'ok' and row.title == 'Tytuł artykułu'
    CitedArticle.objects.filter(pk=row.pk).update(last_checked_at=timezone.now() - timezone.timedelta(days=2))
    fake_get.page = PAGE.replace('1000 zł', '2000 zł')
    with patch.object(sm, '_get', side_effect=fake_get):
        second = sm.run()
    row.refresh_from_db()
    assert second['changed'] == 1 and row.change_count == 1 and row.changed_at and row.check_status == 'zmieniony'
    assert row.changed_archive_url and sm.compare_url(row).startswith('https://web.archive.org/web/diff/')
    assert len(row.history) == 2 and 'akapit' not in str(row.history)
    archives = sm.archives_for([URL])
    assert archives[URL]['changed_at'] == row.changed_at


def test_robots_disallow_means_no_article_fetch(monkeypatch):
    row = CitedArticle.objects.create(url=URL, url_sha256=sm.url_key(URL))
    fetched = []

    def fake_get(url, **kwargs):
        fetched.append(url)
        return response(200, 'User-agent: *\nDisallow: /kraj/')
    from django.core.cache import cache
    cache.clear()
    with patch.object(sm, '_get', side_effect=fake_get):
        assert sm.check(row) == 'robots'
    assert fetched == ['https://www.example-news.pl/robots.txt']


def test_disabled_by_default():
    assert sm.run() == {'status': 'disabled'}


def test_factchecks_need_key_and_flag_and_are_public(monkeypatch):
    row = published([{'claim': 'Polska ma najniższe bezrobocie w UE', 'sources': []}])
    assert fakty.run() == {'status': 'disabled'}
    monkeypatch.setenv('FACTCHECK_ENABLED', 'true')
    monkeypatch.setenv('FACTCHECK_API_KEY', 'test-key')
    item = {'type': 'istniejący fact-check', 'publisher': 'Demagog', 'rating': 'Fałsz', 'url': 'https://demagog.org.pl/x',
            'title': 'Sprawdzamy', 'reviewed_claim': 'Polska ma najniższe bezrobocie'}
    with patch('news.clinic_lab.fact_checks', return_value=[item]) as lookup:
        assert fakty.run()['found'] == 1
        assert fakty.run()['checked'] == 0  # raz na diagnozę
    lookup.assert_called_once()
    row.refresh_from_db()
    assert fakty.public(row) == [{k: item[k] for k in ('publisher', 'rating', 'url', 'title', 'reviewed_claim')}]
    assert row.headline == 'Nagłówek' and row.verdict == 'spin'  # treść diagnozy bez zmian
