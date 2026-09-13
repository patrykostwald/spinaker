import json
from news.metadata import extract_metadata

URL = 'https://publisher.example/news/health'


def test_source_sections_are_topics_not_genres_and_survive_keyword_cap():
    document = {'@type': 'NewsArticle', 'url': URL, 'articleSection': ['Zdrowie', 'Polska'],
                'keywords': [f'słowo {n}' for n in range(20)]}
    raw = ('<meta property="og:type" content="article"><meta property="article:section" content="Medycyna">'
           '<script type="application/ld+json">' + json.dumps(document) + '</script>')
    result = extract_metadata(raw.encode(), URL)
    assert result['tags'][:3] == ['Zdrowie', 'Polska', 'Medycyna']
    assert len(result['tags']) == 12
    assert result['category'] == 'article'


def test_foreign_article_or_listing_does_not_supply_our_topic():
    document = {'@type': 'NewsArticle', 'url': 'https://publisher.example/other', 'articleSection': 'Zdrowie'}
    raw = '<meta property="article:section" content="Gry"><script type="application/ld+json">' + json.dumps(document) + '</script>'
    assert extract_metadata(raw.encode(), URL)['tags'] == []
