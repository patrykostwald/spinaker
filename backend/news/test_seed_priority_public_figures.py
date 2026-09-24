from io import StringIO

import pytest
from django.core.management import call_command

from news.political_models import ParliamentaryRosterEntry, PublicFigure


@pytest.mark.django_db
def test_priority_roster_links_require_exact_external_id_not_a_name_match():
    roster = ParliamentaryRosterEntry.objects.create(
        source='sejm', external_id='246', full_name='Mateusz Morawiecki',
        source_url='https://sejm.example/roster', active=True,
    )
    profile = PublicFigure.objects.create(
        canonical_name='Mateusz Morawiecki', role_category='parliamentary',
        role_title='Poseł na Sejm RP', evidence_url='https://sejm.example/roster',
        import_key='parliamentary:sejm:246', parliamentary_roster_entry=roster,
    )

    call_command('seed_priority_public_figures', stdout=StringIO())

    profile.refresh_from_db()
    assert PublicFigure.objects.filter(canonical_name='Mateusz Morawiecki', archived=False).count() == 1
    assert profile.parliamentary_roster_entry_id == roster.pk
