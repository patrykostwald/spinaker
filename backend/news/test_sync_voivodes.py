from io import StringIO

import pytest
from django.core.management import call_command

from news.management.commands.sync_voivodes import VOIVODES, holder_import_key
from news.political_models import PublicFigure, PublicFigureRole, PublicOffice


@pytest.mark.django_db
def test_sync_voivodes_uses_fixed_official_import_keys_and_never_social_matching():
    output = StringIO()
    call_command('sync_voivodes', stdout=output)

    assert PublicFigure.objects.filter(import_key__startswith='government:voivode:', status='current').count() == 16
    dolnoslaskie = PublicFigure.objects.get(import_key=holder_import_key('dolnoslaskie', 'Anna Żabska'))
    assert dolnoslaskie.canonical_name == 'Anna Żabska'
    assert dolnoslaskie.evidence_url == 'https://www.gov.pl/web/mswia/urzedy-wojewodzkie'
    public_office = PublicOffice.objects.get(import_key='public-office:voivode:dolnoslaskie')
    assert public_office.current_holder == dolnoslaskie
    assert PublicFigureRole.objects.get(public_office=public_office).public_figure == dolnoslaskie
    assert 'Nie utworzono kont X' in output.getvalue()


@pytest.mark.django_db
def test_sync_voivodes_marks_removed_official_key_as_former(monkeypatch):
    PublicFigure.objects.create(
        canonical_name='Były wojewoda', role_category='government', role_title='Wojewoda testowy',
        evidence_url='https://gov.example/roster', import_key='government:voivode:test', status='current',
    )
    monkeypatch.setattr('news.management.commands.sync_voivodes.VOIVODES', VOIVODES[:1])
    call_command('sync_voivodes', stdout=StringIO())
    assert PublicFigure.objects.get(import_key='government:voivode:test').status == 'former'


@pytest.mark.django_db
def test_sync_voivodes_keeps_office_when_holder_changes(monkeypatch):
    monkeypatch.setattr('news.management.commands.sync_voivodes.VOIVODES', (
        ('dolnoslaskie', 'Pierwsza Osoba', 'Wojewoda Dolnośląski', 'Urząd testowy'),
    ))
    call_command('sync_voivodes', stdout=StringIO())
    first = PublicFigure.objects.get(import_key=holder_import_key('dolnoslaskie', 'Pierwsza Osoba'))
    public_office = PublicOffice.objects.get(import_key='public-office:voivode:dolnoslaskie')

    monkeypatch.setattr('news.management.commands.sync_voivodes.VOIVODES', (
        ('dolnoslaskie', 'Druga Osoba', 'Wojewoda Dolnośląski', 'Urząd testowy'),
    ))
    call_command('sync_voivodes', stdout=StringIO())

    public_office.refresh_from_db()
    assert public_office.current_holder.canonical_name == 'Druga Osoba'
    assert PublicFigureRole.objects.get(public_figure=first, public_office=public_office).status == 'former'
