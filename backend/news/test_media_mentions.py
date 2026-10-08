from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from news import media_mentions as mm
from news.models import Article, Source
from news.political_models import PublicFigure, PublicFigureArticleReference


@pytest.fixture(autouse=True)
def clean_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.parametrize('name,text,expected', [
    ('Jan Kowalski', 'JAN KOWALSKI mówi', True),
    ('Jan Kowalski', 'O Janie Kowalskim', False),
    ('Jan Kowalski', 'Z Janem Kowalskim', True),
    ('Jan Kowalski', 'Jana Kowalskiego', True),
    ('Łukasz Wiśniewski', 'Łukasza Wiśniewskiego', True),
    ('Anna Kowalska', 'Z Anną Kowalską', True),
    ('Jan Kowalski', 'Kowalski zabrał głos', False),
    ('Jan Kowalski', 'Jan o reformach Kowalskiego', False),
    ('Jan Kowalski', 'Jan Kowalski-Nowak', False),
    ('Jan Kowalski', 'Adrian Kowalski', False),
    ('Jan Kowalski', 'Jan Kowalskiewicz', False),
    ('Jan Kowalski', 'Jan\u00a0Kowalski', True),
    ('Jan Lis', 'Jan Lis', False),
])
def test_conservative_name_matching(name, text, expected):
    pattern = mm.name_pattern(name)
    assert bool(pattern and pattern.search(text)) is expected


def person(name='Jan Kowalski', **kwargs):
    return PublicFigure.objects.create(canonical_name=name, role_category='political',
                                      role_title='Osoba publiczna', **kwargs)


def article(source, title='Jan Kowalski zabrał głos', **kwargs):
    return Article.objects.create(source=source, title=title,
                                  url=f'https://example.test/{Article.objects.count()}',
                                  published_date=timezone.now(), **kwargs)


@pytest.fixture
def source(db):
    return Source.objects.create(name='Redakcja', url='https://example.test')


@pytest.mark.django_db
def test_separate_mentions_api_deduplicates_and_does_not_write_references(source):
    figure = person()
    title = article(source)
    description = article(source, title='Spotkanie', description='Udział Jana Kowalskiego.')
    confirmed = article(source)
    rejected = article(source)
    for row, status in ((confirmed, 'confirmed'), (rejected, 'rejected')):
        PublicFigureArticleReference.objects.create(public_figure=figure, article=row,
            reference_kind='mentioned', verification_status=status)
    result = APIClient().get(f'/api/public-figures/{figure.pk}/').data
    assert {r['id'] for r in result['mentions']['results']} == {title.pk, description.pk}
    assert 'count' not in result['mentions']
    assert result['materials']['count'] == 1
    desc = next(r for r in result['mentions']['results'] if r['id'] == description.pk)
    assert desc['material_type'] == 'wzmianka'
    assert desc['kind_label'] == 'wzmianka'
    assert PublicFigureArticleReference.objects.count() == 2
    dossier = APIClient().get(f'/api/public-figures/{figure.pk}/dossier/').data
    assert dossier['summary']['confirmed_materials'] == 1
    assert 'mentions' not in dossier
    assert {row['id'] for row in dossier['materials']['results']} == {confirmed.pk}


@pytest.mark.django_db
def test_homonyms_normalized_including_archived_but_not_merged_alias(source):
    figure = person()
    article(source)
    assert mm.mentions_data(figure)['results']
    alias = person(' JAN  KOWALSKI ', archived=True)
    assert mm.mentions_data(figure)['results'] == []
    alias.merged_into = figure
    alias.save()
    assert mm.mentions_data(figure)['results']
    assert mm.mentions_data(alias)['results'] == []
    figure.archived = True
    assert mm.mentions_data(figure)['results'] == []


@pytest.mark.django_db
def test_cache_and_live_exclusion_and_inactive_source(source, monkeypatch, django_assert_num_queries):
    figure = person()
    row = article(source)
    assert mm.mentions_data(figure)['results']
    monkeypatch.setattr(mm, 'matched_field', lambda *args: pytest.fail('Cache missed'))
    with django_assert_num_queries(3):
        assert mm.mentions_data(figure)['results']
    PublicFigureArticleReference.objects.create(public_figure=figure, article=row,
        reference_kind='mentioned', verification_status='rejected')
    assert mm.mentions_data(figure)['results'] == []
    figure.article_references.all().delete()
    source.is_active = False
    source.save()
    assert mm.mentions_data(figure)['results'] == []


@pytest.mark.django_db
def test_hard_candidate_window_and_output_limit(source, monkeypatch, django_assert_num_queries):
    figure = person()
    old = article(source)
    Article.objects.filter(pk=old.pk).update(published_date=timezone.now() - timedelta(days=10))
    for _ in range(4):
        article(source, title='Inny temat')
    monkeypatch.setattr(mm, 'CANDIDATE_LIMIT', 3)
    calls = []
    original = mm.matched_field
    monkeypatch.setattr(mm, 'matched_field', lambda p, a: (calls.append(a['pk']), original(p, a))[1])
    assert mm.mentions_data(figure)['results'] == []
    assert len(calls) == 3 and old.pk not in calls
    cache.clear()
    monkeypatch.setattr(mm, 'CANDIDATE_LIMIT', 2000)
    Article.objects.bulk_create([Article(source=source, title='Jan Kowalski',
        published_date=timezone.now(), url=f'https://example.test/many/{i}') for i in range(105)])
    assert len(mm.mentions_data(figure)['results']) == 100


@pytest.mark.django_db
def test_cached_person_endpoint_rechecks_rejection(source, monkeypatch):
    from types import SimpleNamespace
    from news import przeszlosc_osoba as person_api
    figure = person()
    row = article(source)
    original_mentions = mm.mentions_data(figure)
    key = f'przeszlosc:osoba:v2:{figure.pk}'
    cached = {'id': figure.pk, 'name': figure.canonical_name, 'mentions': original_mentions}
    cache.set(key, cached, 900)
    monkeypatch.setattr('news.przeszlosc.enabled', lambda: True)
    # Only the endpoint cache switch sees PostgreSQL; ORM still uses SQLite.
    monkeypatch.setattr('django.db.connection', SimpleNamespace(vendor='postgresql'))
    monkeypatch.setattr(person_api, 'profile', lambda *a, **kw: pytest.fail('Profile cache missed'))
    client = APIClient()
    url = f'/api/przeszlosc/osoba/{figure.pk}/'
    assert client.get(url).data['mentions']['results'][0]['id'] == row.pk
    PublicFigureArticleReference.objects.create(public_figure=figure, article=row,
        reference_kind='mentioned', verification_status='rejected')
    response = client.get(url)
    assert response.status_code == 200
    assert response.data['mentions']['results'] == []
    assert cache.get(key)['mentions'] == original_mentions


@pytest.mark.django_db
def test_confirmed_profile_type_is_metadata_only_and_dossier_unchanged(source):
    from news.przeszlosc_osoba import profile
    from news.public_figures import dossier_data
    figure = person()
    row = article(source, title='Reportaż: Jan Kowalski odwiedza szkołę')
    PublicFigureArticleReference.objects.create(public_figure=figure, article=row,
        reference_kind='mentioned', verification_status='confirmed')
    result = profile(figure, include_mentions=False)
    material = result['materials']['results'][0]
    assert material['material_type'] == 'reportaz'
    assert material['kind_label'] == 'reportaż'
    assert material['reference_kind'] == 'mentioned'
    assert 'mentions' not in result
    assert 'material_type' not in dossier_data(figure)['materials']['results'][0]
