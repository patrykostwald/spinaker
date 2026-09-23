import csv

import pytest
from django.core.management import call_command

from news.political_models import PublicFigure, SocialHandleEvidence


pytestmark = pytest.mark.django_db


def write_csv(path, rows):
    headers = [
        'official_roster_source', 'official_roster_external_id', 'public_figure_name',
        'role_category', 'role_title', 'proposed_x_handle', 'official_evidence_url',
        'direct_x_url', 'verification_status', 'note',
    ]
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader(); writer.writerows(rows)


def row(**changes):
    data = {
        'official_roster_source': 'official.example', 'official_roster_external_id': 'a-1',
        'public_figure_name': 'Anna Publiczna', 'role_category': 'government', 'role_title': 'Ministra',
        'proposed_x_handle': 'AnnaPubliczna', 'official_evidence_url': 'https://official.example/anna',
        'direct_x_url': 'https://x.com/AnnaPubliczna', 'verification_status': 'confirmed_by_official_link',
        'note': 'Bezpośredni link.',
    }
    data.update(changes)
    return data


def test_import_uses_exact_official_url_not_name(tmp_path):
    profile = PublicFigure.objects.create(canonical_name='Anna Publiczna', role_category='government',
        role_title='Ministra', official_profile_url='https://official.example/anna',
        evidence_url='https://official.example/anna')
    PublicFigure.objects.create(canonical_name='Anna Publiczna', role_category='government',
        role_title='Inna funkcja', evidence_url='https://other.example/anna')
    path = tmp_path / 'x.csv'; write_csv(path, [row()])

    call_command('import_public_figure_x_csv', str(path), apply=True)

    evidence = SocialHandleEvidence.objects.get()
    assert evidence.subject == profile
    assert evidence.status == 'pending_review'


def test_import_leaves_name_only_link_for_manual_connection(tmp_path, capsys):
    PublicFigure.objects.create(canonical_name='Anna Publiczna', role_category='government',
        role_title='Ministra', evidence_url='https://other.example/anna')
    path = tmp_path / 'x.csv'; write_csv(path, [row()])

    call_command('import_public_figure_x_csv', str(path), apply=True)

    assert not SocialHandleEvidence.objects.exists()
    assert 'NIEPOŁĄCZONE' in capsys.readouterr().out
