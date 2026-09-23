from io import StringIO

import pytest
from django.core.management import call_command

from news.political_models import ParliamentaryRosterEntry, PublicFigure


@pytest.mark.django_db
def test_sync_creates_profiles_from_exact_roster_entries_only():
    entry = ParliamentaryRosterEntry.objects.create(
        source='sejm', external_id='123', full_name='Anna Posłanka', club='Klub', district='Warszawa',
        profile_url='https://sejm.example/posel/123', source_url='https://sejm.example/roster', term=10,
        active=True,
    )
    output = StringIO()
    call_command('sync_parliamentary_public_figures', '--source', 'sejm', stdout=output)
    profile = PublicFigure.objects.get(import_key='parliamentary:sejm:123')
    assert profile.parliamentary_roster_entry_id == entry.pk
    assert profile.canonical_name == 'Anna Posłanka'
    assert profile.role_title == 'Poseł na Sejm RP'
    assert 'Nie utworzono kont X' in output.getvalue()


@pytest.mark.django_db
def test_sync_marks_absent_roster_profile_as_former():
    entry = ParliamentaryRosterEntry.objects.create(
        source='senat', external_id='9', full_name='Jan Senator', profile_url='https://senat.example/9',
        source_url='https://senat.example/roster', active=True,
    )
    ParliamentaryRosterEntry.objects.create(
        source='senat', external_id='10', full_name='Aktywna Senatorka', profile_url='https://senat.example/10',
        source_url='https://senat.example/roster', active=True,
    )
    call_command('sync_parliamentary_public_figures', '--source', 'senat', stdout=StringIO())
    entry.active = False
    entry.save(update_fields=['active'])
    call_command('sync_parliamentary_public_figures', '--source', 'senat', stdout=StringIO())
    assert PublicFigure.objects.get(import_key='parliamentary:senat:9').status == 'former'
