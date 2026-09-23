import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from news.political_admin import PublicFigureAdmin
from news.political_models import PublicFigure


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
