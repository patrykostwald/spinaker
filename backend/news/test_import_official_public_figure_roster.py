from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from news.political_models import PublicFigure


HEADERS = 'source_key,canonical_name,role_category,role_title,organisation,official_profile_url,evidence_url,evidence_note\n'
ROW = ('pomorskie,Anna Przykładowa,local,Marszałkini Województwa Pomorskiego,'
       'Urząd Marszałkowski,https://bip.example/profile,https://bip.example/roster,Oficjalny roster.\n')


@pytest.mark.django_db
def test_import_official_roster_uses_source_keys_and_marks_missing_entries_former(tmp_path):
    roster = tmp_path / 'roster.csv'
    roster.write_text(HEADERS + ROW, encoding='utf-8')
    call_command('import_official_public_figure_roster', str(roster), '--scope', 'regional-marshals', '--apply', stdout=StringIO())
    item = PublicFigure.objects.get(import_key='official-roster:regional-marshals:pomorskie')
    assert item.role_category == 'local'

    replacement = tmp_path / 'replacement.csv'
    replacement.write_text(HEADERS + ROW.replace('pomorskie', 'mazowieckie'), encoding='utf-8')
    call_command('import_official_public_figure_roster', str(replacement), '--scope', 'regional-marshals', '--apply', stdout=StringIO())
    item.refresh_from_db()
    assert item.status == 'former'


@pytest.mark.django_db
def test_import_official_roster_rejects_sensitive_columns(tmp_path):
    bad = tmp_path / 'bad.csv'
    bad.write_text(HEADERS.strip() + ',pesel\n' + ROW.replace('\n', ',123\n'), encoding='utf-8')
    with pytest.raises(CommandError, match='niedozwolone'):
        call_command('import_official_public_figure_roster', str(bad), '--scope', 'city-executives')
