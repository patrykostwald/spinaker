"""Metadata identity regressions use synthetic publisher markup; no database I/O."""
import json

import pytest

from news.metadata import extract_metadata


TARGET = 'https://example.org/target'
DATE = '2010-01-01T12:00:00Z'


def extract(nodes, url=TARGET, head=''):
    raw = (head + '<script type="application/ld+json">' + json.dumps(nodes) + '</script>').encode('utf-8')
    return extract_metadata(raw, url)


@pytest.mark.parametrize('nodes', [
    [{'@type': 'NewsArticle', 'datePublished': DATE},
     {'@type': 'NewsArticle', 'url': 'https://example.org/foreign', 'datePublished': DATE}],
    [{'@type': 'NewsArticle', 'datePublished': DATE},
     {'@type': 'NewsArticle', 'url': '/foreign'}],
    {'@type': 'NewsArticle', 'url': TARGET, 'mainEntityOfPage': {'@id': '/foreign'}, 'datePublished': DATE},
    {'@type': 'NewsArticle', 'url': '/foreign', 'mainEntityOfPage': {'@id': TARGET}, 'datePublished': DATE},
    {'@type': 'NewsArticle', 'url': TARGET, 'mainEntityOfPage': {}, 'datePublished': DATE},
    {'@type': 'NewsArticle', 'url': [TARGET], 'datePublished': DATE},
    [{'@type': 'NewsArticle', 'url': TARGET}, {'@type': 'NewsArticle', 'datePublished': DATE}],
    [{'@type': 'NewsArticle', 'url': TARGET, 'datePublished': DATE},
     {'@type': 'NewsArticle', 'url': TARGET, 'datePublished': '2011-01-01T12:00:00Z'}],
])
def test_ambiguous_article_date_is_left_unknown(nodes):
    result = extract(nodes)
    assert result['published_date'] is None
    assert result['date_source'] == ''


@pytest.mark.parametrize('identity', [
    {'url': TARGET},
    {'url': '/target'},
    {'mainEntityOfPage': {'@id': '/target#article'}},
    {'url': '/target/', 'mainEntityOfPage': {'@id': 'https://EXAMPLE.org/target#webpage'}},
    {'url': '//example.org/target'},
])
def test_matching_relative_or_absolute_identity_provides_date(identity):
    result = extract({'@type': 'NewsArticle', **identity, 'datePublished': DATE})
    assert result['published_date'] == '2010-01-01T12:00:00+00:00'
    assert result['date_source'] == 'jsonld:Article.datePublished'


def test_query_parameters_are_part_of_article_identity():
    node = {'@type': 'NewsArticle', 'url': '/target?id=2', 'datePublished': DATE}
    assert extract(node, TARGET + '?id=1')['published_date'] is None
    assert extract(node, TARGET + '?id=2')['published_date'] is not None


def test_matched_article_wins_over_anonymous_and_foreign_dates():
    nodes = {'@graph': [
        {'@type': 'NewsArticle', 'url': TARGET, 'datePublished': DATE},
        {'@type': 'NewsArticle', 'datePublished': '2011-01-01T12:00:00Z'},
        {'@type': 'NewsArticle', 'url': '/foreign', 'datePublished': '2012-01-01T12:00:00Z'},
    ]}
    assert extract(nodes)['published_date'] == '2010-01-01T12:00:00+00:00'


def test_single_anonymous_article_remains_supported():
    assert extract({'@type': 'Article', 'datePublished': DATE})['published_date'] is not None


def test_missing_timezone_is_not_invented():
    assert extract({'@type': 'Article', 'url': TARGET, 'datePublished': '2010-01-01'})['published_date'] is None


def test_jsonld_claim_or_modified_date_is_not_publication_time():
    nodes = [{'@type': 'ClaimReview', 'datePublished': DATE},
             {'@type': 'Article', 'url': TARGET, 'dateModified': DATE}]
    assert extract(nodes)['published_date'] is None


def test_foreign_jsonld_cannot_supply_title_image_or_description():
    foreign = {'@type': 'NewsArticle', 'url': '/foreign', 'headline': 'Foreign title',
               'image': 'https://example.org/foreign.jpg', 'description': 'Foreign summary',
               'datePublished': DATE}
    result = extract(foreign, head='<title>Page title</title><meta property="og:image" content="/page.jpg">'
                                '<meta property="og:description" content="Page description">')
    assert result['title'] == 'Page title'
    assert result['image_url'] == 'https://example.org/page.jpg'
    assert result['description'] == 'Page description'
    without_page_metadata = extract(foreign)
    assert without_page_metadata['title'] == without_page_metadata['image_url'] == without_page_metadata['description'] == ''


def test_explicit_page_publication_meta_stays_separate_from_related_jsonld():
    result = extract({'@type': 'Article', 'url': '/foreign', 'datePublished': DATE},
                     head='<meta property="article:published_time" content="2020-01-01T12:00:00Z">')
    assert result['published_date'] == '2020-01-01T12:00:00+00:00'
    assert result['date_source'] == 'meta:published_time'
