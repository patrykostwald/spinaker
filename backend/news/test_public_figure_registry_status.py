from io import StringIO

import pytest
from django.core.management import call_command

from news.political_models import (ParliamentaryRosterEntry, PublicFigure, PublicOffice,
    PublicFigureRole, SocialHandleEvidence)


@pytest.mark.django_db
def test_registry_status_reports_official_rosters_and_never_needs_private_data(tmp_path):
    roster = ParliamentaryRosterEntry.objects.create(
        source='sejm', external_id='100', full_name='Anna Posłanka',
        source_url='https://sejm.example/roster', term=10, active=True,
    )
    PublicFigure.objects.create(
        canonical_name='Anna Posłanka', role_category='parliamentary',
        role_title='Poseł na Sejm RP', evidence_url='https://sejm.example/roster',
        parliamentary_roster_entry=roster, import_key='parliamentary:sejm:100',
    )
    figure = PublicFigure.objects.get(import_key='parliamentary:sejm:100')
    PublicFigureRole.objects.create(
        public_figure=figure, role_category='party', role_title='Członek władz',
        evidence_url='https://party.example/wladze', import_key='test-role:anna',
    )
    PublicOffice.objects.create(
        import_key='state-office:test', title='Funkcja testowa', role_category='political',
        official_roster_url='https://example.org/funkcja', current_holder=figure,
    )
    SocialHandleEvidence.objects.create(
        roster_entry=roster, handle='anna_poslanka', evidence_url='https://sejm.example/anna',
        extracted_url='https://x.com/anna_poslanka', status='pending_review',
    )
    report_path = tmp_path / 'registry.md'
    output = StringIO()

    call_command('public_figure_registry_status', '--report-path', str(report_path), stdout=output)

    report = report_path.read_text(encoding='utf-8')
    assert 'Sejm RP | 1' in report
    assert 'Parlament krajowy | 1 | 0' in report
    assert 'PESEL' in report
    assert 'Dodatkowe udokumentowane role przy profilach: **1**' in report
    assert 'Trwałe funkcje publiczne w rejestrze: **1**' in report
    assert 'Dowody kont X oczekujące na weryfikację redakcyjną: **1**' in report
    assert 'profiles=1' in output.getvalue()
