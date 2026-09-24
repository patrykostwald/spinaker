"""Offline contract tests; no public HTTP and no active migrations."""
from datetime import datetime, timezone as dt_timezone
import pytest
from django.utils import timezone
from news.models import Article, ImportState, Source
from scraper.institutional_metadata import PILOTS, MetadataPilotError, parse_feed, run_pilot

NIK_RSS = b'''<rss><channel>
<item><title>Wyniki kontroli A</title><link>https://www.nik.gov.pl/aktualnosci/wyniki-a.html</link><pubDate>Sun, 13 Sep 2026 08:30:00 +0200</pubDate><description>BODY MUST NOT BE SAVED</description></item>
<item><title>Wyniki kontroli B</title><link>https://www.nik.gov.pl/aktualnosci/wyniki-b.html</link><pubDate>Mon, 14 Sep 2026 08:30:00 +0200</pubDate></item>
</channel></rss>'''

@pytest.fixture
def nik(db):
    return Source.objects.create(name='NIK pilot', url='https://www.nik.gov.pl/',
        source_type='institution', is_active=True, scrape_enabled=True)

def test_knf_sitemap_filters_publication_families_and_ignores_lastmod():
    raw = b'''<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://www.knf.gov.pl/komunikacja/komunikaty/komunikat-1</loc><lastmod>2026-09-14</lastmod></url><url><loc>https://www.knf.gov.pl/o_nas</loc></url><url><loc>https://evil.example/komunikacja/komunikaty/x</loc></url></urlset>'''
    assert parse_feed(raw, PILOTS['knf']) == [{'url': 'https://www.knf.gov.pl/komunikacja/komunikaty/komunikat-1', 'title': '', 'published_date': None, 'date_raw': ''}]

def test_nik_feed_yields_separate_boxes_and_publisher_dates_only():
    rows = parse_feed(NIK_RSS, PILOTS['nik'])
    assert len(rows) == 2 and rows[0]['published_date'].isoformat() == '2026-09-13T08:30:00+02:00'
    assert all('BODY' not in str(row) for row in rows)

@pytest.mark.django_db
def test_pilot_is_disabled_by_default(nik, monkeypatch):
    monkeypatch.delenv('INSTITUTIONAL_METADATA_PILOT_ENABLED', raising=False)
    monkeypatch.setattr('scraper.institutional_metadata.fetch_feed', lambda _: pytest.fail('network'))
    assert run_pilot(nik.pk, 'nik', cutoff=datetime(2026, 9, 14, tzinfo=dt_timezone.utc))['status'] == 'disabled'
    assert not ImportState.objects.exists()

@pytest.mark.django_db
def test_nik_idempotent_metadata_only_and_frozen_cutoff(nik, monkeypatch):
    monkeypatch.setenv('INSTITUTIONAL_METADATA_PILOT_ENABLED', 'true')
    monkeypatch.setattr('scraper.institutional_metadata.fetch_bounded', lambda *_: NIK_RSS)
    cutoff = datetime(2026, 9, 13, 23, 59, tzinfo=dt_timezone.utc)
    assert run_pilot(nik.pk, 'nik', cutoff=cutoff)['new_records'] == 1
    article = Article.objects.get()
    assert article.source == nik and article.description == '' and article.content.text == ''
    assert article.content.status == 'metadata_only' and 'pozyskano:' in article.evidence_note
    assert run_pilot(nik.pk, 'nik', cutoff=cutoff)['new_records'] == 0
    with pytest.raises(MetadataPilotError, match='cutoff_mismatch'):
        run_pilot(nik.pk, 'nik', cutoff=datetime(2026, 9, 12, tzinfo=dt_timezone.utc))

@pytest.mark.django_db
def test_retry_after_is_kept_in_durable_cursor(nik, monkeypatch):
    import requests
    monkeypatch.setenv('INSTITUTIONAL_METADATA_PILOT_ENABLED', 'true')
    response = requests.Response(); response.status_code = 429; response.headers['Retry-After'] = '1800'
    monkeypatch.setattr('scraper.institutional_metadata.fetch_bounded', lambda *_:
        (_ for _ in ()).throw(requests.HTTPError('429', response=response)))
    before = timezone.now()
    assert run_pilot(nik.pk, 'nik', cutoff=datetime(2026, 9, 14, tzinfo=dt_timezone.utc))['status'] == 'error'
    state = ImportState.objects.get()
    assert datetime.fromisoformat(state.cursor['available_at']) >= before + timezone.timedelta(seconds=1799)

@pytest.mark.django_db
def test_source_disabled_during_fetch_prevents_all_article_writes(nik, monkeypatch):
    monkeypatch.setenv('INSTITUTIONAL_METADATA_PILOT_ENABLED', 'true')
    def disable(*_):
        Source.objects.filter(pk=nik.pk).update(scrape_enabled=False)
        return NIK_RSS
    monkeypatch.setattr('scraper.institutional_metadata.fetch_bounded', disable)
    result = run_pilot(nik.pk, 'nik', cutoff=datetime(2026, 9, 14, tzinfo=dt_timezone.utc))
    assert result['status'] == 'disabled' and not Article.objects.exists()

def test_feed_batch_is_bounded_and_rejects_foreign_urls():
    items = ''.join(f'<item><title>T {i}</title><link>https://www.nik.gov.pl/a/{i}</link></item>' for i in range(40))
    assert len(parse_feed(f'<rss><channel>{items}</channel></rss>'.encode(), PILOTS['nik'])) == 25
    assert parse_feed(b'<rss><channel><item><title>X</title><link>https://evil.example/x</link></item></channel></rss>', PILOTS['nik']) == []
