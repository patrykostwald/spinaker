import json
from pathlib import Path
from unittest.mock import patch

import pytest

from news.models import Source
from scraper.rss_scraper import seed_sources


def verified_sources():
    return json.loads((Path(__file__).parent / 'data' / 'verified_local_sources.json').read_text(encoding='utf-8'))


@pytest.mark.django_db
def test_verified_seed_is_offline_idempotent_and_preserves_editor_settings():
    first = verified_sources()[0]
    source = Source.objects.create(name='Nazwa redakcyjna', url=first['url'],
        rss_url='https://custom.example/feed', scrape_frequency_minutes=2,
        is_active=False, scrape_enabled=False)
    with patch('scraper.rss_scraper.fetch_feed') as fetch:
        seed_sources()
        count = Source.objects.count()
        seed_sources()
        fetch.assert_not_called()
    assert Source.objects.count() == count
    source.refresh_from_db()
    assert source.name == 'Nazwa redakcyjna'
    assert source.rss_url == 'https://custom.example/feed'
    assert source.scrape_frequency_minutes == 2
    assert not source.is_active and not source.scrape_enabled


@pytest.mark.django_db
def test_sitemap_only_sources_are_not_assigned_fictional_rss():
    seed_sources()
    sitemap_sources = [s for s in verified_sources() if s['sitemap_urls'] and not s['rss_url']]
    assert sitemap_sources
    assert Source.objects.filter(url__in=[s['url'] for s in sitemap_sources], rss_url='').count() == len(sitemap_sources)
    assert Source.objects.get(url='https://ddwloclawek.pl').rss_url == ''
    assert Source.objects.get(name='Radio Poznań').rss_url == 'https://radiopoznan.fm/rss/informacje'


@pytest.mark.django_db
def test_seed_preserves_owner_identity_exclusion_rss_and_custom_frequency():
    from scraper.utils import get_or_create_source
    seed_sources()
    source = Source.objects.get(name='Onet Wiadomości')
    source_id = source.pk
    original_url = source.url
    original_key = source.catalog_seed_key
    count = Source.objects.count()
    source.name = 'Nazwa wybrana przez właściciela'
    source.url = 'https://www.onet.pl/informacje/adres-redakcyjny'
    source.rss_url = 'https://wiadomosci.onet.pl/feed-wlasciciela'
    source.scrape_frequency_minutes = 19
    source.catalog_stage = 'excluded'
    source.is_active = False
    source.scrape_enabled = False
    source.save()
    seed_sources()
    source.refresh_from_db()
    assert Source.objects.count() == count
    assert source.catalog_seed_key == original_key
    assert source.name == 'Nazwa wybrana przez właściciela'
    assert source.url == 'https://www.onet.pl/informacje/adres-redakcyjny'
    assert source.rss_url == 'https://wiadomosci.onet.pl/feed-wlasciciela'
    assert source.scrape_frequency_minutes == 19
    assert source.catalog_stage == 'excluded' and not source.is_active and not source.scrape_enabled
    assert get_or_create_source(name='Onet Wiadomości', url=original_url).pk == source_id


@pytest.mark.django_db
def test_candidate_identity_is_adopted_before_owner_edits_url():
    spec = verified_sources()[0]
    candidate = Source.objects.create(name='Kandydat właściciela', url=spec['url'], catalog_stage='candidate',
        is_active=False, scrape_enabled=False, scrape_frequency_minutes=37)
    assert candidate.catalog_seed_key  # API and command use this same save path.
    # Cover records created by bulk operations that intentionally bypass Model.save().
    Source.objects.filter(pk=candidate.pk).update(catalog_seed_key=None)
    seed_sources()
    candidate.refresh_from_db()
    original_key = candidate.catalog_seed_key
    assert original_key
    count = Source.objects.count()
    candidate.url = spec['url'].rstrip('/') + '/adres-wlasciciela'
    candidate.save()
    seed_sources()
    candidate.refresh_from_db()
    assert candidate.catalog_seed_key == original_key and Source.objects.count() == count
    assert candidate.catalog_stage == 'candidate' and not candidate.is_active and not candidate.scrape_enabled
    assert candidate.scrape_frequency_minutes == 37
