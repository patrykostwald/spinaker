import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import RequestFactory

from news.political_admin import PublicFigureAdmin
from news.political_models import ParliamentaryRosterEntry, PublicFigure


pytestmark = pytest.mark.django_db


def figure(**overrides):
    values = {
        'canonical_name': 'Przykładowa Osoba',
        'role_category': 'government',
        'role_title': 'Minister',
        'organisation': 'Ministerstwo Przykładowe',
        'status': 'current',
        'evidence_url': 'https://www.gov.pl/web/przyklad/osoba',
    }
    values.update(overrides)
    return PublicFigure.objects.create(**values)


def test_public_figure_is_separate_from_mandates_and_social_intake():
    record = figure()
    assert record.archived is False
    assert not hasattr(record, 'social_handle_evidence')
    assert record.get_role_category_display() == 'Rząd i administracja'


def test_same_name_is_allowed_when_official_evidence_describes_different_roles():
    first = figure(canonical_name='Jan Kowalski', evidence_url='https://example.org/one')
    second = figure(canonical_name='Jan Kowalski', role_category='local', role_title='Burmistrz',
        evidence_url='https://example.org/two')
    assert first.pk != second.pk


def test_public_figure_archives_without_deleting():
    record = figure()
    PublicFigure.objects.filter(pk=record.pk).update(archived=True)
    record.refresh_from_db()
    assert record.archived is True
    assert PublicFigure.objects.filter(pk=record.pk).exists()


def test_admin_disables_delete_and_only_archives_records():
    record = figure()
    admin_view = PublicFigureAdmin(PublicFigure, __import__('django.contrib.admin', fromlist=['site']).site)
    user = get_user_model().objects.create_superuser('editor', 'editor@example.test', 'password')
    request = RequestFactory().post('/admin/news/publicfigure/')
    request.user = user
    assert admin_view.has_delete_permission(request, record) is False
    admin_view.archive_selected(request, PublicFigure.objects.filter(pk=record.pk))
    record.refresh_from_db()
    assert record.archived is True


def test_priority_seed_uses_explicit_evidence_and_links_only_exact_roster_names():
    ParliamentaryRosterEntry.objects.create(
        source='sejm', external_id='246', full_name='Mateusz Morawiecki', club='Klub',
        profile_url='https://sejm.example/morawiecki', source_url='https://sejm.example', active=True,
    )
    ParliamentaryRosterEntry.objects.create(
        source='ep', external_id='257067', full_name='Grzegorz Braun', club='',
        profile_url='https://ep.example/braun', source_url='https://ep.example', active=True,
    )
    cabinet = figure(canonical_name='Paulina Hennig-Kloska', import_key='kprm-cabinet:paulina')

    call_command('seed_priority_public_figures')

    morawiecki = PublicFigure.objects.get(import_key='editorial-priority:mateusz-morawiecki')
    braun = PublicFigure.objects.get(import_key='editorial-priority:grzegorz-braun')
    korwin = PublicFigure.objects.get(import_key='editorial-priority:janusz-korwin-mikke')
    cabinet.refresh_from_db()
    assert morawiecki.parliamentary_roster_entry.full_name == 'Mateusz Morawiecki'
    assert braun.parliamentary_roster_entry.full_name == 'Grzegorz Braun'
    assert cabinet.parliamentary_roster_entry is None
    assert korwin.evidence_url == 'https://korwin.com.pl/wladze/'
    assert PublicFigure.objects.filter(canonical_name='Paulina Hennig-Kloska').count() == 1
