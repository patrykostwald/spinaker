from io import StringIO

import pytest
from django.core.management import call_command

from news.management.commands.sync_voivodes import VOIVODES
from news.political_models import PublicFigure


@pytest.mark.django_db
def test_sync_voivodes_uses_fixed_official_import_keys_and_never_social_matching():
    output = StringIO()
    call_command('sync_voivodes', stdout=output)

    assert PublicFigure.objects.filter(import_key__startswith='government:voivode:', status='current').count() == 16
    dolnoslaskie = PublicFigure.objects.get(import_key='government:voivode:dolnoslaskie')
    assert dolnoslaskie.canonical_name == 'Anna Żabska'
    assert dolnoslaskie.evidence_url == 'https://www.gov.pl/web/mswia/urzedy-wojewodzkie'
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
