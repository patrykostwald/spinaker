import pytest
from django.utils import timezone
from news.models import Source, ArchiveJob, Article, ImportState
from scraper.html_archive import parse_listing,run_kprm_listing,START_URL
from scraper.archive import SourceDelay


def html(page=1,next_page=2,last_page=3,article='test-entry',date='09.09.2026'):
    next_link=f'<a id="js-pagination-page-next" href="?page={next_page}&size=10"></a>' if next_page else ''
    return f'''<div class="art-prev"><ul><li><img src="/photo/test.jpg"><div class="event"><span class="date">{date}</span></div><div class="title"><a href="/web/premier/{article}">Tytuł źródłowy</a></div></li></ul></div><input id="js-pagination-page" value="{page}"><a id="js-pagination-pages-count" href="?page={last_page}&size=10">{last_page}</a>{next_link}'''.encode()

@pytest.fixture
def source(db):
    return Source.objects.create(name='KPRM test',url='https://www.gov.pl/web/premier/rss',catalog_stage='configured',is_active=True,scrape_enabled=True)


def due(source):
    state=ImportState.objects.get(name=f'html-archive:kprm:{source.pk}')
    state.cursor['available_at']=timezone.now().isoformat();state.save(update_fields=['cursor'])


def test_listing_reads_publisher_links_without_inventing_dates():
    result=parse_listing(html(date='02.09.2029'),START_URL)
    assert result['records'][0]['listing_date_raw']=='02.09.2029'
    assert result['next_url']==START_URL+'?page=2&size=10'
    assert 'published_date' not in result['records'][0]
    with pytest.raises(ValueError): parse_listing(html(next_page=None),START_URL)
    with pytest.raises(ValueError): parse_listing(html().replace(b'?page=2&size=10',b'https://evil.test/a'),START_URL)
    with pytest.raises(ValueError): parse_listing(b'<html>Access denied</html>',START_URL)


def test_resumes_and_only_enqueues_urls(source,monkeypatch):
    urls=[]
    def fetch(url):
        urls.append(url)
        return html() if len(urls)==1 else html(page=2,next_page=None,last_page=2,article='older-entry')
    monkeypatch.setattr('scraper.html_archive.fetch_listing',fetch)
    result=run_kprm_listing(source.pk)
    assert result['queued']==1
    assert Article.objects.count()==0
    assert ArchiveJob.objects.get().source_id==source.pk
    assert run_kprm_listing(source.pk)['status']=='deferred'
    due(source)
    assert run_kprm_listing(source.pk)['status']=='complete'
    assert urls==[START_URL,START_URL+'?page=2&size=10']
    assert run_kprm_listing(source.pk)['status']=='complete'
    assert ArchiveJob.objects.count()==2


def test_error_retries_same_page_and_preserves_existing_job(source,monkeypatch):
    existing=ArchiveJob.objects.create(source=source,url='https://www.gov.pl/web/premier/test-entry',status='error',attempts=5,last_error='preserve')
    monkeypatch.setattr('scraper.html_archive.fetch_listing',lambda url:b'invalid')
    assert run_kprm_listing(source.pk)['status']=='error'
    assert run_kprm_listing(source.pk)['status']=='deferred'
    due(source)
    monkeypatch.setattr('scraper.html_archive.fetch_listing',lambda url:html())
    assert run_kprm_listing(source.pk)['queued']==0
    existing.refresh_from_db();assert existing.attempts==5 and existing.status=='error'

@pytest.mark.parametrize('field,value',[('is_active',False),('scrape_enabled',False),('catalog_stage','excluded')])
def test_disabled_never_fetches(source,monkeypatch,field,value):
    setattr(source,field,value);source.save()
    monkeypatch.setattr('scraper.html_archive.fetch_listing',lambda url:pytest.fail('network'))
    assert run_kprm_listing(source.pk)['status']=='disabled'
    assert not ImportState.objects.exists()


def test_disabled_while_fetching_does_not_enqueue(source,monkeypatch):
    def fetch(url):
        Source.objects.filter(pk=source.pk).update(is_active=False)
        return html()
    monkeypatch.setattr('scraper.html_archive.fetch_listing',fetch)
    assert run_kprm_listing(source.pk)['status']=='disabled'
    assert ArchiveJob.objects.count()==0


def test_host_delay_is_not_failure(source,monkeypatch):
    def fetch(url): raise SourceDelay()
    monkeypatch.setattr('scraper.html_archive.fetch_listing',fetch)
    assert run_kprm_listing(source.pk)['status']=='deferred'
    state=ImportState.objects.get();assert state.cursor['failures']==0

def test_event_date_is_separate_from_publication_and_not_from_listing():
    from scraper.html_archive import extract_kprm_metadata
    raw=b'<title>Publisher title</title><a href="/web/premier/wydarzenia">Back</a><article id="main-content" class="article-area__article"><h2>Title</h2><p class="event-date">09.09.2026</p></article>'
    result=extract_kprm_metadata(raw,'https://www.gov.pl/web/premier/test-entry')
    assert result['event_date']=='2026-09-09'
    assert result['published_date'] is None
    assert result['publisher_type']=='article'
    with pytest.raises(ValueError): extract_kprm_metadata(html(),'https://www.gov.pl/web/premier/wydarzenia')
    with pytest.raises(ValueError): extract_kprm_metadata(b'<p class="event-date">09.09.2026</p>','https://www.gov.pl/web/premier/foo')


def test_retry_after_is_honored():
    from scraper.html_archive import retry_delay
    from types import SimpleNamespace
    exc=ValueError();exc.response=SimpleNamespace(headers={'Retry-After':'3600'})
    assert retry_delay(exc,1)==3600


def test_completed_archive_checks_latest_hourly_without_reimporting_history(source,monkeypatch):
    from datetime import timedelta
    from django.utils import timezone
    monkeypatch.setattr('scraper.html_archive.fetch_listing',lambda url:html())
    run_kprm_listing(source.pk)
    state=ImportState.objects.get()
    state.cursor={'complete':True,'pages_completed':296}
    state.last_success=timezone.now()-timedelta(hours=2)
    state.save()
    result=run_kprm_listing(source.pk)
    assert result['status']=='complete' and result['queued']==0
    state.refresh_from_db()
    assert state.cursor['refresh'] is True and state.cursor['pages_completed']==1
