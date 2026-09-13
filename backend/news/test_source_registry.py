import pytest
from news.external_search import SourceRegistry, allowed_sources, match_source
from news.ai_research import archive_result, validate_result, ResearchError
from news.models import Source, Article
from news.test_ai_research import provider_result


@pytest.fixture
def institutions(db):
    return [Source.objects.create(name=name, url='https://www.gov.pl/web/' + slug,
            source_type='institution', is_active=True, scrape_enabled=True)
            for name, slug in [('KPRM', 'premier'), ('Zdrowie', 'zdrowie')]]


def test_shared_host_registry_preserves_scopes_without_widening_domains(institutions):
    sources = allowed_sources()
    assert sorted(sources) == ['www.gov.pl']
    assert len(sources.all_sources) == 2
    assert match_source('https://gov.pl/web/premier/komunikat', sources) == institutions[0]
    assert match_source('https://www.gov.pl/web/zdrowie/komunikat', sources) == institutions[1]
    for url in ['https://gov.pl/web/obce/komunikat', 'https://gov.pl/web/premier-obce/a',
                'https://gov.pl/ogolne', 'https://gov.pl.evil.test/web/premier/a',
                'https://gov.pl/web/premier/../obce/a']:
        assert match_source(url, sources) is None


def test_ambiguous_and_excluded_institutions_never_resolve(institutions):
    duplicate = Source.objects.create(name='Duplicate', url='https://gov.pl/web/premier/rss', source_type='institution')
    assert match_source('https://gov.pl/web/premier/a', SourceRegistry([institutions[0], duplicate])) is None
    institutions[1].catalog_stage = 'excluded'
    institutions[1].save()
    assert match_source('https://gov.pl/web/zdrowie/a', allowed_sources()) is None


def test_result_keeps_correct_shared_host_articles(institutions):
    sources = allowed_sources()
    first = Article.objects.create(source=institutions[0], url='https://gov.pl/web/premier/a', title='KPRM')
    second = Article.objects.create(source=institutions[1], url='https://gov.pl/web/zdrowie/b', title='Zdrowie')
    wrong = Article.objects.create(source=institutions[1], url='https://gov.pl/web/premier/c', title='Wrong identity')
    refs = [{'url': a.url} for a in [first, second, wrong]]
    result = archive_result({'sources': refs, 'sections': []}, 'context', sources, enqueue=False)
    ids = [a['id'] for group in result['archive_timeline'].values() for a in group]
    assert set(ids) == {first.pk, second.pk}
    assert validate_result(provider_result(second.url), sources)['sources'][0]['source_name'] == 'Zdrowie'
    with pytest.raises(ResearchError):
        validate_result(provider_result('https://gov.pl/web/obce/a'), sources)
