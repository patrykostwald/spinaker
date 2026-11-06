import csv

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command

from news import przeszlosc_doniesienia as pd
from news.political_models import PublicFigure, PublicFigureMediaMention, RegisteredOrganisation

pytestmark = pytest.mark.django_db


@pytest.fixture
def figure():
    return PublicFigure.objects.create(canonical_name='Jan Kowalski', role_category='parliamentary', role_title='Poseł')


@pytest.fixture
def org():
    return RegisteredOrganisation.objects.create(name='Fundacja Testowa Pomocy', krs_number='0000012345', kind='foundation',
                                                 official_register_url='https://ekrs.ms.gov.pl/x')


def mention(figure, org, **kw):
    data = dict(public_figure=figure, organisation=org, category='mention', match_basis='identifier',
                source_url='https://portal.example/artykul', source_title='Tytuł artykułu', source_outlet='Portal', quote='Krótki cytat.')
    data.update(kw)
    return PublicFigureMediaMention.objects.create(**data)


def staff():
    return get_user_model().objects.create_user('redaktor', 'r@example.com', 'x', is_staff=True)


def test_new_mention_is_not_public_until_published(figure, org):
    m = mention(figure, org)
    assert m.status == 'pending_review' and pd.mentions_for(figure)['count'] == 0
    m.publish(staff())
    body = pd.mentions_for(figure)
    assert body['count'] == 1 and body['results'][0]['organisation']['url'] == '/przeszlosc/spolka/0000012345'
    assert body['results'][0]['unconfirmed'] is False and 'nie jest dowodem powiązania' in body['notice']


def test_name_only_match_is_marked_unconfirmed_and_categories_are_ordered(figure, org):
    staff_user = staff()
    other = mention(figure, org, category='other', source_url='https://a.example/1', match_basis='name_only')
    alleged = mention(figure, org, category='alleged', source_url='https://a.example/2')
    for m in (other, alleged):
        m.publish(staff_user)
    results = pd.mentions_for(figure)['results']
    assert [r['category'] for r in results] == ['alleged', 'other'] and results[1]['unconfirmed'] is True


def test_editing_published_mention_returns_it_to_review(figure, org):
    m = mention(figure, org)
    m.publish(staff())
    m.category = 'alleged'
    m.save()
    m.refresh_from_db()
    assert m.status == 'pending_review' and m.reviewed_at is None and pd.mentions_for(figure)['count'] == 0


def test_validation_and_publication_rules(figure, org):
    with pytest.raises(ValidationError):
        mention(figure, org, source_url='ftp://x.example/a').full_clean()
    with pytest.raises(ValidationError):
        mention(figure, org, source_url='https://b.example/1', quote='x' * 301).full_clean()
    m = mention(figure, org, source_url='https://b.example/2')
    with pytest.raises(ValidationError):
        m.publish(get_user_model().objects.create_user('zwykly', 'z@example.com', 'x'))


def test_archived_organisation_and_rejected_are_hidden(figure, org):
    m = mention(figure, org)
    m.publish(staff())
    org.archived = True
    org.save()
    assert pd.mentions_for(figure)['count'] == 0


def test_import_goes_to_review_queue_and_rejects_bad_rows(figure, org, tmp_path):
    path = tmp_path / 'd.csv'
    rows = [
        {'public_figure_id': figure.pk, 'krs_number': '12345', 'category': 'alleged', 'source_url': 'https://c.example/1',
         'source_title': 'Tytuł', 'source_outlet': 'Portal', 'published_on': '2026-11-01', 'quote': 'Cytat', 'match_basis': 'identifier'},
        {'public_figure_id': figure.pk, 'krs_number': '99999', 'category': 'mention', 'source_url': 'https://c.example/2', 'source_title': 'T'},
        {'public_figure_id': figure.pk, 'krs_number': '12345', 'category': 'zla', 'source_url': 'https://c.example/3', 'source_title': 'T'},
    ]
    with path.open('w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['public_figure_id', 'krs_number', 'category', 'source_url', 'source_title', 'source_outlet', 'published_on', 'quote', 'match_basis'])
        w.writeheader()
        w.writerows(rows)
    call_command('przeszlosc_doniesienia_import', str(path))
    assert PublicFigureMediaMention.objects.count() == 0            # bez --apply nic nie zapisuje
    call_command('przeszlosc_doniesienia_import', str(path), '--apply')
    m = PublicFigureMediaMention.objects.get()
    assert m.status == 'pending_review' and m.collected_by == 'import' and pd.mentions_for(figure)['count'] == 0
    call_command('przeszlosc_doniesienia_import', str(path), '--apply')
    assert PublicFigureMediaMention.objects.count() == 1            # ponowny import nie dubluje


def test_organisation_carries_link_to_official_register(figure, org):
    mention(figure, org).publish(staff())
    assert pd.mentions_for(figure)['results'][0]['organisation']['register_url'] == 'https://ekrs.ms.gov.pl/x'
