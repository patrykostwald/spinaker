from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from news.political_models import OfficialVideoChannel, PublicFigure


pytestmark = pytest.mark.django_db


def test_stages_direct_official_youtube_channel_only_after_apply():
    figure = PublicFigure.objects.create(canonical_name='Anna Publiczna', role_category='political',
        role_title='Osoba publiczna', evidence_url='https://example.org/person')
    args = ('--subject-type', 'public-figure', '--subject-id', str(figure.pk),
        '--channel-url', 'https://www.youtube.com/@AnnaPubliczna',
        '--evidence-url', 'https://example.org/person', '--display-name', 'Anna Publiczna')
    call_command('register_official_youtube_channel', *args, stdout=StringIO())
    assert not OfficialVideoChannel.objects.exists()
    call_command('register_official_youtube_channel', *args, '--apply', stdout=StringIO())
    channel = OfficialVideoChannel.objects.get()
    assert channel.subject == figure
    assert channel.status == 'pending_review'
    assert channel.collection_enabled is False


def test_rejects_search_results_and_does_not_write():
    figure = PublicFigure.objects.create(canonical_name='Anna Publiczna', role_category='political',
        role_title='Osoba publiczna', evidence_url='https://example.org/person')
    with pytest.raises(CommandError, match='bezpośredni link HTTPS'):
        call_command('register_official_youtube_channel', '--subject-type', 'public-figure',
            '--subject-id', str(figure.pk), '--channel-url', 'https://www.youtube.com/results?search_query=anna',
            '--evidence-url', 'https://example.org/person', '--apply', stdout=StringIO())
    assert not OfficialVideoChannel.objects.exists()
