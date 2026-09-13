import pytest
from news.classification import publisher_category
from news.metadata import extract_metadata
from news.models import Source
from scraper.utils import upsert_article

SPONSORED_URL = 'https://ddwloclawek.pl/pl/701_artykuly-sponsorowane/98474_zadaszenie-balkonu-jak-wybrac-rozwiazanie-dopasowane-do-budynku.html'


def test_known_publisher_sponsored_section_has_evidence_in_preview():
    metadata = extract_metadata(b'<title>Publisher title</title><meta property="og:type" content="article">', SPONSORED_URL)
    assert metadata['category'] == 'sponsored'
    assert '701_artykuly-sponsorowane' in metadata['category_evidence']
    assert metadata['title'] == 'Publisher title'


@pytest.mark.parametrize('url', [
    'https://other.example/pl/701_artykuly-sponsorowane/123_story.html',
    'https://ddwloclawek.pl.evil.example/pl/701_artykuly-sponsorowane/123_story.html',
    'https://ddwloclawek.pl/pl/11_wiadomosci/123_story.html?next=/pl/701_artykuly-sponsorowane/',
    'https://ddwloclawek.pl/pl/701_artykuly-sponsorowane/',
])
def test_rule_is_not_a_keyword_or_host_substring_heuristic(url):
    assert publisher_category(url, 'article') == ('article', '')


@pytest.mark.django_db
@pytest.mark.parametrize('method', ['rss', 'archive'])
def test_automatic_import_records_sponsorship_without_rewriting_source_text(method):
    source = Source.objects.create(name='Publisher', url='https://ddwloclawek.pl')
    article, created = upsert_article(source=source, title='Publisher headline', url=SPONSORED_URL,
        published_date=None, description='Publisher description', ingestion_method=method)
    assert created and article.category == 'sponsored' and article.evidence_note
    assert article.title == 'Publisher headline' and article.description == 'Publisher description'
    article.category = 'reportage'
    article.category_reviewed = True
    article.save()
    repeated, created = upsert_article(source=source, title='Later headline', url=SPONSORED_URL,
        published_date=None, ingestion_method=method)
    assert not created and repeated.category == 'reportage'
    assert repeated.title == 'Publisher headline'
