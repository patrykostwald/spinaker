from io import StringIO

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command

from news.political_models import PublicFigure, SocialHandleEvidence


@pytest.mark.django_db
def test_x_evidence_queue_reports_only_staged_evidence_without_creating_accounts(tmp_path):
    figure = PublicFigure.objects.create(
        canonical_name='Anna Publiczna', role_category='government', role_title='Ministra testów',
        evidence_url='https://gov.example/anna', import_key='government:test:anna',
    )
    SocialHandleEvidence.objects.create(
        subject_content_type=ContentType.objects.get_for_model(PublicFigure), subject_object_id=figure.pk,
        handle='anna_publiczna', evidence_url='https://gov.example/anna',
        extracted_url='https://x.com/anna_publiczna', status='pending_review',
    )
    report_path = tmp_path / 'queue.md'
    output = StringIO()

    call_command('public_figure_x_evidence_queue', '--report-path', str(report_path), stdout=output)

    report = report_path.read_text(encoding='utf-8')
    assert 'Anna Publiczna' in report
    assert '@anna_publiczna' in report
    assert 'Do weryfikacji redakcyjnej: **1**' in report
    assert 'pending_review=1' in output.getvalue()
