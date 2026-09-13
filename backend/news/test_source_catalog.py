import csv
import io
import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from rest_framework.test import APIClient

from news.models import Article, ArchiveJob, Source, ImportState
from news.admin import SourceAdmin


@pytest.fixture
def editor(db):
    return get_user_model().objects.create_user(username='catalog-editor', is_staff=True)


@pytest.fixture
def client(editor):
    client = APIClient()
    client.force_authenticate(editor)
    return client


@pytest.fixture(autouse=True)
def public_dns():
    with patch('news.source_catalog.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('8.8.8.8', 443))]) as resolve:
        yield resolve


@pytest.mark.django_db
def test_catalog_access_requires_staff(editor):
    client = APIClient()
    source = Source.objects.create(name='Known', url='https://example.org')
    for user in (None, get_user_model().objects.create_user(username='catalog-reader')):
        client.force_authenticate(user)
        assert client.get('/api/editor/sources/').status_code == 403
        assert client.get('/api/editor/sources/export/').status_code == 403
        assert client.post('/api/editor/sources/', {'name': 'New'}, format='json').status_code == 403
        assert client.patch(f'/api/editor/sources/{source.pk}/', {'name': 'Changed'}, format='json').status_code == 403


@pytest.mark.django_db
def test_new_candidates_are_inactive_and_missing_urls_are_not_invented(client):
    for name in ('Brak adresu A', 'Brak adresu B'):
        response = client.post('/api/editor/sources/', {'name': name, 'source_type': 'portal'}, format='json')
        assert response.status_code == 201, response.data
        assert response.data['url'] == ''
        assert response.data['catalog_stage'] == 'candidate'
        assert response.data['is_active'] is False and response.data['scrape_enabled'] is False
    assert Source.objects.filter(url__isnull=True).count() == 2


@pytest.mark.django_db
def test_catalog_rejects_private_urls_and_bad_configuration(client, public_dns):
    for url in ('http://localhost', 'http://127.0.0.1', 'http://[::1]', 'https://user:password@example.org/',
                'file:///etc/passwd', 'https://host.internal/', 'https://example.org:bad'):
        response = client.post('/api/editor/sources/', {'name': 'Invalid', 'url': url}, format='json')
        assert response.status_code == 400, (url, response.data)
    public_dns.return_value = [(2, 1, 6, '', ('192.168.1.5', 443))]
    assert client.post('/api/editor/sources/', {'name': 'DNS private', 'url': 'https://example.org'}, format='json').status_code == 400
    assert client.post('/api/editor/sources/', {'name': 'Zero', 'scrape_frequency_minutes': 0}, format='json').status_code == 400
    assert client.post('/api/editor/sources/', {'name': 'Active candidate', 'is_active': True}, format='json').status_code == 400
    assert client.post('/api/editor/sources/', {'name': 'No URL', 'catalog_stage': 'configured'}, format='json').status_code == 400
    assert Source.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize('with_article', [True, False])
def test_domain_and_records_are_preserved_but_source_can_be_disabled(client, with_article):
    source = Source.objects.create(name='Source', url='https://example.org/feed', rss_url='https://example.org/feed')
    job = ArchiveJob.objects.create(source=source, url='https://example.org/article', kind='page')
    article = Article.objects.create(source=source, url=job.url, title='Oryginalny tytuł') if with_article else None
    response = client.patch(f'/api/editor/sources/{source.pk}/', {'url': 'https://different.example.org'}, format='json')
    assert response.status_code == 400
    assert client.delete(f'/api/editor/sources/{source.pk}/').status_code == 405
    response = client.patch(f'/api/editor/sources/{source.pk}/', {'is_active': False, 'scrape_enabled': False}, format='json')
    assert response.status_code == 200, response.data
    source.refresh_from_db(); job.refresh_from_db()
    assert not source.is_active and not source.scrape_enabled
    assert source.url == 'https://example.org/feed' and job.source_id == source.pk
    if article:
        article.refresh_from_db()
        assert article.title == 'Oryginalny tytuł' and article.source_id == source.pk
    assert response.data['archive_status']['pending'] == 1
    assert response.data['article_count'] == int(with_article)
    assert not SourceAdmin(Source, None).has_delete_permission(None, source)


@pytest.mark.django_db(transaction=True)
def test_dns_checks_precede_write_transaction(client, public_dns):
    source = Source.objects.create(name='New', url='https://old.example.org', is_active=False, scrape_enabled=False)
    def verify_unlocked(*args, **kwargs):
        assert not connection.in_atomic_block
        return [(2, 1, 6, '', ('8.8.8.8', 443))]
    public_dns.side_effect = verify_unlocked
    response = client.patch(f'/api/editor/sources/{source.pk}/', {'url': 'https://new.example.org'}, format='json')
    assert response.status_code == 200, response.data
    assert public_dns.called


@pytest.mark.django_db
def test_all_sources_and_csv_are_complete_and_csv_formulas_are_escaped(client):
    Source.objects.bulk_create([Source(name=f'Kandydat {i}', catalog_stage='candidate', is_active=False,
                                      scrape_enabled=False, url=None) for i in range(63)])
    Source.objects.create(name='=HYPERLINK("https://example.org")', url=None, catalog_stage='candidate',
                          is_active=False, scrape_enabled=False, catalog_notes='Zażółć\nDruga linia')
    result = client.get('/api/editor/sources/').json()
    assert len(result['sources']) == 64
    assert {'value': 'institution', 'label': 'Instytucja'} in result['source_types']
    response = client.get('/api/editor/sources/export/')
    assert response.status_code == 200 and response.content.startswith(b'\xef\xbb\xbf')
    rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig')), delimiter=';'))
    assert len(rows) == 64
    formula = next(row for row in rows if 'HYPERLINK' in row['name'])
    assert formula['name'].startswith("'=") and formula['catalog_notes'] == 'Zażółć\nDruga linia'


@pytest.mark.django_db
def test_catalog_session_write_requires_csrf(editor):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(editor)
    assert client.get('/api/editor/sources/').status_code == 200
    assert client.post('/api/editor/sources/', {'name': 'Unsafe'}, format='json').status_code == 403
    token = client.get('/api/auth/csrf/').json()['csrfToken']
    response = client.post('/api/editor/sources/', {'name': 'Protected'}, format='json', HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 201


@pytest.mark.django_db
def test_source_check_is_distinct_from_import_configuration_and_detects_staleness(client):
    source = Source.objects.create(name='Measured publisher', url='https://example.org', rss_url='https://example.org/feed')
    Article.objects.create(source=source, url='https://example.org/old', title='Dated article', published_date='2008-09-03T10:00:00Z')
    assert next(row for row in client.get('/api/editor/sources/').json()['sources'] if row['id']==source.pk)['access_check'] is None
    ImportState.objects.create(name=f'source-check:{source.pk}', cursor={'checked_at':'2026-09-09T17:00:00Z',
        'source_url':source.url, 'configured_rss_url':source.rss_url,
        'rss':{'status':'unavailable','url':source.rss_url},'archive':{'status':'sitemap','sitemap_urls':['https://example.org/sitemap.xml']}})
    row = client.get('/api/editor/sources/').json()['sources'][0]
    assert row['is_active'] is True and row['access_check']['rss']['status']=='unavailable'
    assert row['oldest_publication'].startswith('2008-09-03')
    assert row['access_check']['configuration_changed'] is False
    source.rss_url='https://example.org/new-feed'; source.save(update_fields=['rss_url'])
    assert client.get('/api/editor/sources/').json()['sources'][0]['access_check']['configuration_changed'] is True


@pytest.mark.django_db
def test_candidates_import_is_complete_idempotent_and_preserves_exclusion(tmp_path):
    known = Source.objects.create(name='Existing publisher', url='https://example.org/rss/original',
        rss_url='https://example.org/feed', scrape_frequency_minutes=2, catalog_stage='excluded',
        is_active=False, scrape_enabled=False, catalog_notes='Notatka właściciela')
    csv_path = tmp_path / 'sources.csv'
    csv_path.write_text('nazwa;adres;dowod_url\nInna nazwa;https://www.example.org/nowy;https://catalog.example.org/a\n'
                       'Nieznany adres A;;https://catalog.example.org/b\nNieznany adres B;;https://catalog.example.org/c\n'
                       'Nowy portal;https://new.example.org;https://catalog.example.org/d\n', encoding='utf-8-sig')
    official_path = tmp_path / 'official.json'
    official_path.write_text(json.dumps([{'name': 'Instytucja', 'publisher_url': 'https://official.example.org',
        'source_identity_url': 'https://official.example.org/rss', 'status': 'candidate_html_listing_not_enabled'}]), encoding='utf-8')
    options = {'media_csv': str(csv_path), 'official_json': str(official_path)}
    call_command('import_source_candidates', stdout=io.StringIO(), **options)
    assert Source.objects.count() == 5
    notes = dict(Source.objects.values_list('pk', 'catalog_notes'))
    call_command('import_source_candidates', stdout=io.StringIO(), **options)
    assert Source.objects.count() == 5 and notes == dict(Source.objects.values_list('pk', 'catalog_notes'))
    known.refresh_from_db()
    assert known.catalog_stage == 'excluded' and not known.is_active and not known.scrape_enabled
    assert known.scrape_frequency_minutes == 2 and known.rss_url == 'https://example.org/feed'
    assert known.catalog_notes.startswith('Notatka właściciela') and 'Inna nazwa' in known.catalog_notes
    assert Source.objects.filter(url__isnull=True).count() == 2
    assert not Source.objects.exclude(pk=known.pk).filter(is_active=True).exists()


@pytest.mark.django_db
def test_candidate_can_be_excluded_and_never_enabled_without_configuration(client):
    source = Source.objects.create(name='No address', url=None, catalog_stage='candidate', is_active=False, scrape_enabled=False)
    response = client.patch(f'/api/editor/sources/{source.pk}/', {'catalog_stage': 'excluded'}, format='json')
    assert response.status_code == 200 and response.data['catalog_stage'] == 'excluded'
    response = client.patch(f'/api/editor/sources/{source.pk}/', {'is_active': True, 'scrape_enabled': True}, format='json')
    assert response.status_code == 400
    source.refresh_from_db()
    assert source.catalog_stage == 'excluded' and not source.is_active and not source.scrape_enabled


@pytest.mark.django_db
def test_official_candidate_import_never_merges_distinct_institutions_by_domain(tmp_path):
    existing = Source.objects.create(name='Ministerstwo Finansów', url='https://www.gov.pl/web/finanse/rss',
        source_type='institution', catalog_notes='Istniejąca instytucja')
    known = Source.objects.create(name='KPRM', url='https://www.gov.pl/web/premier/rss', source_type='institution')
    known.name = 'Własna nazwa KPRM'
    known.url = 'https://www.gov.pl/web/premier'
    known.catalog_stage = 'excluded'
    known.is_active = False; known.scrape_enabled = False
    known.save()
    media = tmp_path / 'media.csv'; media.write_text('nazwa;adres\n', encoding='utf-8')
    official = tmp_path / 'official.json'
    official.write_text(json.dumps([
        {'name': 'Nowa instytucja', 'publisher_url': 'https://www.gov.pl/web/nowa-instytucja'},
        {'name': 'KPRM', 'publisher_url': 'https://www.gov.pl/web/premier',
         'source_identity_url': 'https://www.gov.pl/web/premier/rss'},
    ]), encoding='utf-8')
    options = {'media_csv': str(media), 'official_json': str(official), 'stdout': io.StringIO()}
    call_command('import_source_candidates', **options)
    call_command('import_source_candidates', **options)
    assert Source.objects.count() == 3
    existing.refresh_from_db(); known.refresh_from_db()
    assert existing.catalog_notes == 'Istniejąca instytucja'
    assert known.name == 'Własna nazwa KPRM' and known.catalog_stage == 'excluded'
    assert 'KPRM' in known.catalog_notes
    new = Source.objects.get(name='Nowa instytucja')
    assert new.catalog_stage == 'candidate' and not new.is_active and not new.scrape_enabled
