from unittest.mock import patch

import pytest
from django.core.management import call_command

from news.government_roster import CabinetRow, cabinet_office_import_key
from news.political_models import PublicFigure, PublicFigureRole, PublicOffice

SOURCE_URL = 'https://www.gov.pl/web/premier/czlonkowie-rady-ministrow2'
TITLE = 'wiceprezes Rady Ministrów, minister cyfryzacji'


def cabinet_profile():
    figure = PublicFigure.objects.create(canonical_name='Krzysztof Gawkowski', role_category='government', role_title=TITLE,
                                         organisation='Rada Ministrów', import_key='kprm-cabinet:krzysztof-gawkowski',
                                         evidence_url=SOURCE_URL)
    office = PublicOffice.objects.create(import_key=cabinet_office_import_key(TITLE), title=TITLE, role_category='government',
                                         organisation='Rada Ministrów', official_roster_url=SOURCE_URL, current_holder=figure)
    PublicFigureRole.objects.create(public_figure=figure, public_office=office, role_category='government', role_title=TITLE,
                                    organisation='Rada Ministrów', evidence_url=SOURCE_URL,
                                    import_key=f'{office.import_key}:holder:{figure.import_key}')
    return figure, office


def mp_profile():
    return PublicFigure.objects.create(canonical_name='Krzysztof Gawkowski', role_category='parliamentary', role_title='Poseł na Sejm RP',
                                       organisation='Sejm Rzeczypospolitej Polskiej', import_key='parliamentary:sejm:90',
                                       evidence_url='https://www.sejm.gov.pl')


@pytest.mark.django_db
def test_plan_changes_nothing_and_apply_moves_office_and_role():
    source, office = cabinet_profile()
    target = mp_profile()

    call_command('merge_public_figure_profiles')
    source.refresh_from_db()
    assert not source.archived and source.merged_into_id is None

    call_command('merge_public_figure_profiles', '--apply')
    source.refresh_from_db()
    office.refresh_from_db()
    assert source.archived and source.merged_into_id == target.pk
    assert office.current_holder_id == target.pk
    assert target.public_roles.filter(public_office=office, archived=False).exists()


@pytest.mark.django_db
def test_cabinet_sync_keeps_merged_profile_archived_and_office_on_target():
    source, office = cabinet_profile()
    target = mp_profile()
    call_command('merge_public_figure_profiles', '--apply')

    rows = [CabinetRow(canonical_name='Krzysztof Gawkowski', role_title=TITLE, source_url=SOURCE_URL,
                       import_key='kprm-cabinet:krzysztof-gawkowski')]
    with patch('news.management.commands.sync_public_figures.cabinet_rows', return_value=rows):
        call_command('sync_public_figures', '--source', 'cabinet')

    source.refresh_from_db()
    office.refresh_from_db()
    assert source.archived
    assert office.current_holder_id == target.pk
    assert PublicFigure.objects.filter(canonical_name='Krzysztof Gawkowski', archived=False).count() == 1


@pytest.mark.django_db
def test_restore_splits_profiles_again():
    source, office = cabinet_profile()
    target = mp_profile()
    call_command('merge_public_figure_profiles', '--apply')

    call_command('merge_public_figure_profiles', '--restore', '--apply')

    source.refresh_from_db()
    office.refresh_from_db()
    assert not source.archived and source.merged_into_id is None
    assert office.current_holder_id == source.pk
    assert source.public_roles.filter(public_office=office).exists()
    assert not target.public_roles.filter(public_office=office).exists()
