from io import StringIO

import pytest
from django.core.management import call_command

from news.political_models import ParliamentaryRosterEntry, PublicFigure, PublicFigureRole
from news.public_figures import figure_data


@pytest.mark.django_db
def test_normalizer_merges_only_profiles_with_same_exact_roster_entry():
    entry = ParliamentaryRosterEntry.objects.create(
        source='sejm', external_id='7', full_name='Anna Posłanka', source_url='https://sejm.example/list', active=True,
    )
    canonical = PublicFigure.objects.create(
        canonical_name='Anna Posłanka', role_category='parliamentary', role_title='Poseł na Sejm RP',
        organisation='Sejm RP', evidence_url='https://sejm.example/list',
        import_key='parliamentary:sejm:7', parliamentary_roster_entry=entry,
    )
    duplicate = PublicFigure.objects.create(
        canonical_name='Anna Posłanka', role_category='government', role_title='Minister testów',
        organisation='Rada Ministrów', evidence_url='https://gov.example/cabinet',
        import_key='kprm-cabinet:anna-poslanka', parliamentary_roster_entry=entry,
    )
    unrelated = PublicFigure.objects.create(
        canonical_name='Anna Posłanka', role_category='party', role_title='Rola partyjna',
        evidence_url='https://party.example/leadership', import_key='manual:anna',
    )

    call_command('normalize_public_figure_roster_duplicates', stdout=StringIO())

    duplicate.refresh_from_db()
    unrelated.refresh_from_db()
    assert duplicate.archived is True
    assert unrelated.archived is False
    assert PublicFigureRole.objects.filter(public_figure=canonical).count() == 2
    roles = figure_data(canonical, include_detail=True)['roles']
    assert {role['role_title'] for role in roles} == {'Poseł na Sejm RP', 'Minister testów'}
