import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from news.political_models import PublicFigure, SocialHandleEvidence


pytestmark = pytest.mark.django_db


def test_command_queues_explicit_public_figure_x_evidence_without_polling():
    figure = PublicFigure.objects.create(canonical_name='Ministra Publiczna', role_category='government', role_title='Ministra',
        evidence_url='https://gov.example/profile')
    call_command('register_public_figure_x_evidence', '--figure-id', str(figure.pk), '--handle', '@MinisterPL',
        '--evidence-url', 'https://gov.example/profile', '--x-url', 'https://x.com/MinisterPL', '--apply')
    evidence = SocialHandleEvidence.objects.get()
    assert evidence.subject == figure and evidence.status == 'pending_review'
    assert evidence.candidate is None


def test_command_rejects_non_x_or_missing_public_figure():
    with pytest.raises(CommandError, match='Nie znaleziono'):
        call_command('register_public_figure_x_evidence', '--figure-id', '99', '--handle', 'MinisterPL',
            '--evidence-url', 'https://gov.example/profile', '--x-url', 'https://x.com/MinisterPL')
    figure = PublicFigure.objects.create(canonical_name='Ministra Publiczna', role_category='government', role_title='Ministra',
        evidence_url='https://gov.example/profile')
    with pytest.raises(CommandError, match='x-url'):
        call_command('register_public_figure_x_evidence', '--figure-id', str(figure.pk), '--handle', 'MinisterPL',
            '--evidence-url', 'https://gov.example/profile', '--x-url', 'https://example.org/account')
