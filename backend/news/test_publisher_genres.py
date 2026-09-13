import json
import pytest
from news.metadata import extract_metadata
from news.classification import normalize_publisher_tags
from news.models import Source
from scraper.utils import upsert_article

URL = 'https://example.org/news/a'


def metadata(node, prefix=''):
    return extract_metadata((prefix + '<script type="application/ld+json">' + json.dumps(node) + '</script>').encode(), URL)


@pytest.mark.parametrize('kind,expected', [('InterviewNewsArticle', 'interview'), ('ReportageNewsArticle', 'reportage'), ('VideoObject', 'video'), ('PodcastEpisode', 'podcast')])
def test_explicit_matched_genres(kind, expected):
    result = metadata({'@type': kind, 'url': URL, 'keywords': ['Energia', 'Polska']})
    assert result['category'] == expected and result['declared_genre'] == expected
    assert result['category_evidence'] and result['tags'] == ['Energia', 'Polska']


def test_titles_topics_and_listing_recommendations_not_genres():
    result = metadata({'@type': 'Article', 'url': URL, 'headline': 'Wywiad o reklamie', 'keywords': ['Reklama', 'Sponsorowane']})
    assert result['category'] == 'article' and result['declared_genre'] == ''
    assert result['tags'] == ['Reklama', 'Sponsorowane']
    result = metadata({'@type': 'CollectionPage', 'mainEntity': {'@type': 'InterviewNewsArticle', 'url': 'https://example.org/other'}})
    assert result['category'] == 'other' and not result['tags']
    result = metadata({'@type': 'InterviewNewsArticle', 'headline': 'Anonymous card'})
    assert result['category'] == 'other'
    result = metadata({'@type': 'Article', 'url': URL, 'genre': 'sponsored'})
    assert result['category'] == 'article'


def test_exact_declared_genre_conflicts_and_bounded_tags():
    assert metadata({'@type': 'Article', 'url': URL, 'genre': 'Wywiad'})['category'] == 'interview'
    assert metadata({'@type': 'Article', 'url': URL, 'genre': 'Wywiad o polityce'})['category'] == 'article'
    assert metadata({'@type': 'InterviewNewsArticle', 'url': URL, 'genre': 'podcast'})['category'] == 'article'
    tags = normalize_publisher_tags([{'term': '<b>Polska</b>'}, 'POLSKA', 'x' * 100] + list(map(str, range(20))))
    assert len(tags) == 12 and tags[:2] == ['Polska', 'x' * 80]


@pytest.mark.django_db
def test_upsert_specializes_only_default_and_preserves_source_facts():
    source = Source.objects.create(name='Publisher', url='https://example.org')
    args = dict(source=source, title='Original', url=URL, published_date='2024-01-02T12:00:00Z', ingestion_method='rss')
    article, _ = upsert_article(**args)
    date = article.published_date
    changed, created = upsert_article(**{**args, 'title': 'Changed', 'published_date': '2025-01-01T12:00:00Z'},
        declared_genre='interview', category_evidence='Publisher genre proof', tags=['Energia'])
    assert not created and changed.category == 'interview'
    assert changed.title == 'Original' and changed.published_date == date and changed.tags == ['Energia']
    changed.category_reviewed = True
    changed.category = 'article'
    changed.save()
    changed, _ = upsert_article(**args, declared_genre='podcast', category_evidence='Proof', tags=['New'])
    assert changed.category == 'article' and changed.tags == ['Energia']


@pytest.mark.django_db
def test_rss_category_is_topic_not_sponsorship(monkeypatch):
    from scraper.rss_scraper import scrape_rss_source
    from news.models import Article
    source = Source.objects.create(name='Publisher', url='https://example.org', rss_url='https://example.org/rss', is_active=True)
    feed = b'<rss version="2.0"><channel><title>News</title><link>https://example.org</link><description>News</description><item><title>Wywiad o reklamie</title><link>https://example.org/news/a</link><category>Reklama</category><category>Sponsorowane</category></item></channel></rss>'
    monkeypatch.setattr('scraper.rss_scraper.fetch_feed', lambda url: feed)
    scrape_rss_source(source.pk)
    article = Article.objects.get(url=URL)
    assert article.category == 'article' and article.tags == ['Reklama', 'Sponsorowane']
