import json
from datetime import timedelta
from types import SimpleNamespace
from urllib.robotparser import RobotFileParser
import pytest
from django.utils import timezone
from news.models import Source, ArchiveJob, ImportState, SourceAccessInstruction
from scraper.archive import discover, process, _HOST_STATES, same_host
from scraper.news_sitemaps import news_sitemap_cycle
from scraper.news_sitemaps import verified_maps


def approve_sitemap(source):
    version = (SourceAccessInstruction.objects.filter(source=source)
        .order_by('-version').values_list('version', flat=True).first() or 0) + 1
    return SourceAccessInstruction.objects.create(
        source=source, version=version, status='approved', channel='sitemap',
        allowed_scope='metadata', endpoint=source.url,
        terms_url='https://example.org/terms', evidence={'basis': 'test'},
        reviewed_at=timezone.now(), reviewed_by='test', minimum_interval_seconds=3)


def test_archive_map_matches_rss_source_and_requires_explicit_approval(tmp_path, monkeypatch):
    path = tmp_path / 'catalog.json'
    row = {'name': 'Polsat News', 'url': 'https://www.polsatnews.pl',
        'sitemap_urls': ['https://www.polsatnews.pl/sitemap.xml'],
        'archive_verification': {'status': 'verified', 'can_backfill': True}}
    path.write_text(json.dumps([row]), encoding='utf-8')
    monkeypatch.setattr('scraper.news_sitemaps.CATALOG_PATH', path)
    source = SimpleNamespace(name='Polsat News', url='https://www.polsatnews.pl/rss/polska.xml')
    assert verified_maps(source, require_archive_approval=True) == row['sitemap_urls']
    row['archive_verification']['can_backfill'] = False
    path.write_text(json.dumps([row]), encoding='utf-8')
    assert verified_maps(source, require_archive_approval=True) == []


def test_archive_map_allows_only_explicit_publisher_alias_host(tmp_path, monkeypatch):
    path = tmp_path / 'catalog.json'
    row = {'name': 'Interia', 'url': 'https://fakty.interia.pl/feed',
        'sitemap_hosts': ['wydarzenia.interia.pl'],
        'sitemap_urls': ['https://wydarzenia.interia.pl/sitemap/index.xml'],
        'archive_verification': {'status': 'verified', 'can_backfill': True}}
    path.write_text(json.dumps([row]), encoding='utf-8')
    monkeypatch.setattr('scraper.news_sitemaps.CATALOG_PATH', path)
    source = SimpleNamespace(name='Interia', url='https://fakty.interia.pl/feed')
    assert verified_maps(source, require_archive_approval=True) == row['sitemap_urls']
    row['sitemap_urls'] = ['https://attacker.example/sitemap.xml']
    path.write_text(json.dumps([row]), encoding='utf-8')
    assert verified_maps(source, require_archive_approval=True) == []


def test_www_alias_is_same_publisher_host():
    assert same_host('https://www.example.org/map.xml', 'https://example.org/feed')


@pytest.mark.django_db
def test_sitemap_index_enqueues_only_configured_article_children(setup_maps, monkeypatch):
    source = Source.objects.create(name='A', url='https://example.org')
    setup_maps(source)
    from scraper import news_sitemaps
    news_sitemaps.CATALOG_PATH.write_text(json.dumps([{
        'name': 'A', 'url': source.url,
        'archive_sitemap_child_patterns': [r'/post-sitemap[0-9]+\.xml$'],
        'archive_verification': {'status': 'verified', 'can_backfill': True},
    }]), encoding='utf-8')
    job = ArchiveJob.objects.create(source=source, url='https://example.org/index.xml', kind='sitemap')
    xml = '<sitemapindex><sitemap><loc>https://example.org/post-sitemap1.xml</loc></sitemap>' \
          '<sitemap><loc>https://example.org/tag-sitemap1.xml</loc></sitemap></sitemapindex>'
    monkeypatch.setattr('scraper.archive.fetch_feed', lambda *_, **__: xml.encode())
    _HOST_STATES.clear(); process(job)
    assert ArchiveJob.objects.filter(url='https://example.org/post-sitemap1.xml').exists()
    assert not ArchiveJob.objects.filter(url='https://example.org/tag-sitemap1.xml').exists()


@pytest.fixture
def setup_maps(tmp_path, monkeypatch):
    def configure(source, maps=None, news=None):
        approve_sitemap(source)
        path = tmp_path / 'catalog.json'
        path.write_text(json.dumps([{'url': source.url,
            'sitemap_urls': maps or [], 'news_sitemap_urls': news or []}]), encoding='utf-8')
        monkeypatch.setattr('scraper.news_sitemaps.CATALOG_PATH', path)
        policy = RobotFileParser(); policy.parse(['User-agent: *', 'Allow: /'])
        monkeypatch.setattr('scraper.archive.robots', lambda *_, **__: policy)
        return policy
    return configure


@pytest.mark.django_db
def test_verified_fallback_without_rss_or_robots_maps_is_idempotent(setup_maps):
    source = Source.objects.create(name='TV', url='https://example.org', rss_url='')
    setup_maps(source, maps=['https://example.org/archive.xml'] * 2 +
        ['https://other.org/map.xml', 'javascript:bad', 'https://example.org/' + 'a'*1100])
    assert discover(source) == 1
    assert discover(source) == 0
    assert ArchiveJob.objects.get().url == 'https://example.org/archive.xml'


@pytest.mark.django_db
def test_robot_and_verified_maps_union_and_foreign_owner_preserved(setup_maps):
    source = Source.objects.create(name='A', url='https://example.org')
    other = Source.objects.create(name='B', url='https://other.org')
    policy = setup_maps(source, maps=['https://example.org/archive.xml'])
    policy.parse(['User-agent: *', 'Allow: /', 'Sitemap: https://example.org/robots.xml'])
    job = ArchiveJob.objects.create(source=other, url='https://example.org/archive.xml',
        kind='sitemap', status='done', checked_at=timezone.now()-timedelta(days=2))
    assert discover(source) == 1
    job.refresh_from_db(); assert job.status == 'done' and job.source_id == other.pk


@pytest.mark.django_db
@pytest.mark.parametrize('change', [{'is_active':False}, {'scrape_enabled':False}, {'catalog_stage':'excluded'}])
def test_stale_source_cannot_revive_dispatch_or_discovery(setup_maps, change):
    source = Source.objects.create(name='A', url='https://example.org')
    setup_maps(source, maps=['https://example.org/all.xml'],news=['https://example.org/news.xml'])
    Source.objects.filter(pk=source.pk).update(**change)
    assert discover(source) == 0
    assert news_sitemap_cycle()['queued_maps'] == 0
    assert not ArchiveJob.objects.exists()


@pytest.mark.django_db
def test_small_map_dispatch_persistent_interval_and_no_archive_promotion(setup_maps):
    source = Source.objects.create(name='A', url='https://example.org',scrape_frequency_minutes=15)
    setup_maps(source, maps=['https://example.org/all.xml'], news=['https://example.org/news.xml']*2)
    assert news_sitemap_cycle()['queued_maps'] == 1
    job = ArchiveJob.objects.get(); assert job.priority == 10
    ArchiveJob.objects.filter(pk=job.pk).update(status='done')
    assert news_sitemap_cycle()['dispatched_sources'] == 0
    state=ImportState.objects.get(); state.last_success -= timedelta(minutes=16);state.save()
    assert news_sitemap_cycle()['queued_maps'] == 1
    job.refresh_from_db(); assert job.status == 'pending'
    assert not ArchiveJob.objects.filter(url__endswith='all.xml').exists()
    assert ImportState.objects.get().cursor['meaning'] == 'queue_dispatch_only'


@pytest.mark.django_db
@pytest.mark.parametrize('status', ['pending','running','error'])
def test_dispatch_does_not_reset_lease_backoff_attempts_or_priority(setup_maps,status):
    source=Source.objects.create(name='A',url='https://example.org')
    setup_maps(source,news=['https://example.org/news.xml'])
    lease=timezone.now()+timedelta(hours=6)
    job=ArchiveJob.objects.create(source=source,url='https://example.org/news.xml',kind='sitemap',
        status=status,available_at=lease,attempts=4,last_error='timeout',priority=22)
    assert news_sitemap_cycle()['queued_maps']==0
    job.refresh_from_db()
    assert (job.status,job.available_at,job.attempts,job.last_error,job.priority)==(status,lease,4,'timeout',22)


@pytest.mark.django_db
def test_news_children_priority_keeps_foreign_owner_and_error_backoff(setup_maps,monkeypatch):
    source=Source.objects.create(name='A',url='https://example.org')
    other=Source.objects.create(name='B',url='https://other.org')
    setup_maps(source)
    job=ArchiveJob.objects.create(source=source,url='https://example.org/news.xml',kind='sitemap',priority=10)
    lease=timezone.now()+timedelta(hours=4)
    protected=ArchiveJob.objects.create(source=source,url='https://example.org/error',kind='page',status='error',available_at=lease)
    foreign=ArchiveJob.objects.create(source=other,url='https://example.org/foreign',kind='page',priority=0)
    pending=ArchiveJob.objects.create(source=source,url='https://example.org/pending',kind='page',available_at=lease)
    xml='<urlset>'+''.join('<url><loc>https://example.org/'+x+'</loc></url>' for x in ['new','new','error','foreign','pending'])+'</urlset>'
    monkeypatch.setattr('scraper.archive.fetch_feed',lambda *_, **__:xml.encode())
    _HOST_STATES.clear(); process(job)
    assert ArchiveJob.objects.get(url='https://example.org/new').priority==10
    protected.refresh_from_db(); assert protected.available_at==lease and protected.status=='error' and protected.priority==0
    foreign.refresh_from_db(); assert foreign.source_id==other.pk and foreign.priority==0
    pending.refresh_from_db(); assert pending.priority==10 and pending.available_at==lease


@pytest.mark.django_db
def test_source_disabled_during_robots_fetch_cannot_enqueue(setup_maps,monkeypatch):
    source=Source.objects.create(name='A',url='https://example.org')
    policy=setup_maps(source,maps=['https://example.org/all.xml'])
    def disabled(*_, **__):
        Source.objects.filter(pk=source.pk).update(is_active=False)
        return policy
    monkeypatch.setattr('scraper.archive.robots',disabled)
    assert discover(source)==0
    assert not ArchiveJob.objects.exists()
