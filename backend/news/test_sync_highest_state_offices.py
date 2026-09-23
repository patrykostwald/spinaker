from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from news.political_models import PublicFigure, PublicFigureRole


def _senator(external_id):
    return PublicFigure.objects.create(
        canonical_name=f'Senator {external_id}', role_category='parliamentary',
        role_title='Senator Rzeczypospolitej Polskiej',
        organisation='Senat Rzeczypospolitej Polskiej',
        evidence_url='https://senat.example/roster',
        import_key=f'parliamentary:senat:{external_id}',
    )


@pytest.mark.django_db
def test_sync_highest_state_offices_uses_fixed_senate_roster_keys_only():
    for external_id in ('1063', '1051', '1085', '1016', '1072'):
        _senator(external_id)

    output = StringIO()
    call_command('sync_highest_state_offices', stdout=output)

    president = PublicFigure.objects.get(import_key='state-office:president:current')
    assert president.canonical_name == 'Karol Nawrocki'
    assert PublicFigureRole.objects.filter(import_key__startswith='state-office:senate-presidium:').count() == 5
    assert PublicFigureRole.objects.get(import_key='state-office:senate-presidium:marshal').public_figure.import_key == 'parliamentary:senat:1063'
    assert 'Nie utworzono kont X' in output.getvalue()


@pytest.mark.django_db
def test_sync_highest_state_offices_fails_closed_without_exact_senate_profiles():
    _senator('1063')
    with pytest.raises(CommandError, match='Brakuje profilu'):
        call_command('sync_highest_state_offices', stdout=StringIO())
