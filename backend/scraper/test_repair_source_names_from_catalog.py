from io import StringIO

import pytest
from django.core.management import call_command

from news.models import Source
from scraper.management.commands.prepare_justice_candidates import (
    CANDIDATE_NOTE, DISTRICT_PROSECUTORS, NATIONAL_JUSTICE, REGIONAL_PROSECUTORS)


def _find_entry_with_diacritic(pairs, char):
    for name, url in pairs:
        if char in name:
            return name, url
    raise AssertionError(f'no catalog entry contains {char!r}')


def _corrupt(text):
    for ch in 'ąćęłńóśżźĄĆĘŁŃÓŚŻŹ':
        text = text.replace(ch, '?')
    return text


def _create_full_justice_catalog(corrupt_names=True, corrupt_notes=True):
    note = _corrupt(CANDIDATE_NOTE) if corrupt_notes else CANDIDATE_NOTE
    for name, url in list(NATIONAL_JUSTICE) + list(REGIONAL_PROSECUTORS):
        Source.objects.create(
            name=_corrupt(name) if corrupt_names else name, url=url, catalog_notes=note)
    for name in DISTRICT_PROSECUTORS:
        Source.objects.create(
            name=_corrupt(name) if corrupt_names else name, url=None, catalog_notes=note)


@pytest.mark.django_db
def test_dry_run_reports_without_writing():
    name, url = _find_entry_with_diacritic(NATIONAL_JUSTICE, 'ą')
    source = Source.objects.create(name='placeholder', url=url, catalog_notes=CANDIDATE_NOTE)
    corrupted = name.replace('ą', '?')
    Source.objects.filter(pk=source.pk).update(name=corrupted)

    out = StringIO()
    call_command('repair_source_names_from_catalog', stdout=out)
    source.refresh_from_db()
    assert source.name == corrupted
    assert 'names: changed=1' in out.getvalue()
    assert 'dry_run' in out.getvalue()


@pytest.mark.django_db
def test_apply_restores_url_matched_name_and_is_idempotent():
    name, url = _find_entry_with_diacritic(NATIONAL_JUSTICE, 'ą')
    source = Source.objects.create(name='placeholder', url=url, catalog_notes=CANDIDATE_NOTE)
    Source.objects.filter(pk=source.pk).update(name=name.replace('ą', '?'))

    out = StringIO()
    call_command('repair_source_names_from_catalog', apply=True, stdout=out)
    source.refresh_from_db()
    assert source.name == name
    assert 'names: changed=1' in out.getvalue()

    out2 = StringIO()
    call_command('repair_source_names_from_catalog', apply=True, stdout=out2)
    assert 'names: changed=0' in out2.getvalue()


@pytest.mark.django_db
def test_catalog_notes_repaired_for_any_matching_candidate_row():
    source = Source.objects.create(
        name='Prokuratura Krajowa', url=NATIONAL_JUSTICE[0][1],
        catalog_notes=_corrupt(CANDIDATE_NOTE))
    call_command('repair_source_names_from_catalog', apply=True, stdout=StringIO())
    source.refresh_from_db()
    assert source.catalog_notes == CANDIDATE_NOTE


def _changed_count(names):
    return sum(1 for name in names if _corrupt(name) != name)


@pytest.mark.django_db
def test_district_prosecutors_repaired_only_when_block_is_exactly_contiguous():
    _create_full_justice_catalog()
    expected = _changed_count([n for n, _u in list(NATIONAL_JUSTICE) + list(REGIONAL_PROSECUTORS)]) \
        + _changed_count(DISTRICT_PROSECUTORS)

    out = StringIO()
    call_command('repair_source_names_from_catalog', apply=True, stdout=out)
    assert f'names: changed={expected}' in out.getvalue()
    for name in DISTRICT_PROSECUTORS:
        assert Source.objects.filter(name=name).exists()


@pytest.mark.django_db
def test_district_prosecutors_untouched_if_an_extra_row_breaks_the_expected_shape():
    _create_full_justice_catalog()
    # An unrelated extra row that happens to share the corrupted-note prefix
    # breaks the "exactly 41 consecutive rows" assumption; the command must
    # refuse the positional match rather than risk assigning a wrong name.
    Source.objects.create(name='Nieznany kandydat', url=None, catalog_notes=CANDIDATE_NOTE)
    expected = _changed_count([n for n, _u in list(NATIONAL_JUSTICE) + list(REGIONAL_PROSECUTORS)])

    out = StringIO()
    call_command('repair_source_names_from_catalog', apply=True, stdout=out)
    for name in DISTRICT_PROSECUTORS:
        assert not Source.objects.filter(name=name).exists()
    # URL-addressable names and catalog_notes are still safely fixed either way.
    assert f'names: changed={expected}' in out.getvalue()


@pytest.mark.django_db
def test_source_with_no_matching_url_is_left_untouched():
    out = StringIO()
    call_command('repair_source_names_from_catalog', apply=True, stdout=out)
    assert 'names: changed=0' in out.getvalue()
