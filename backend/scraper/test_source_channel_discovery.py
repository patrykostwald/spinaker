import pytest

from news.models import Source, SourceType
from scraper.source_channel_discovery import inspect_explicit_channel
from scraper.management.commands.discover_confirmable_source_channels import is_fresh


class FakeNetwork:
    def __init__(self, pages):
        self.pages = pages

    def fetch(self, url):
        return self.pages[url], url, []


@pytest.mark.django_db
def test_channel_discovery_only_accepts_explicit_working_feed():
    source = Source.objects.create(name='Office', url='https://office.example', source_type=SourceType.INSTITUTION,
        catalog_stage='candidate', is_active=False, scrape_enabled=False)
    result = inspect_explicit_channel(source, {
        'legal_terms_discovery': {'terms_pages': [{'url': 'https://office.example/reuse'}]},
    }, FakeNetwork({
        'https://office.example': b'<a href="/rss.xml">RSS</a>',
        'https://office.example/reuse': b'<p>Reuse conditions.</p>',
        'https://office.example/rss.xml': b'<rss><channel><item><title>News</title><link>https://office.example/news</link></item></channel></rss>',
    }))
    assert result['status'] == 'working_channel_requires_editorial_card_review'
    assert result['channels'][0]['url'] == 'https://office.example/rss.xml'


@pytest.mark.django_db
def test_channel_discovery_freshness_requires_matching_source_signature():
    source = Source.objects.create(name='Office', url='https://office.example', source_type=SourceType.INSTITUTION,
        catalog_stage='candidate', is_active=False, scrape_enabled=False)
    assert not is_fresh(source, {'legal_channel_discovery': {'version': 1}})
