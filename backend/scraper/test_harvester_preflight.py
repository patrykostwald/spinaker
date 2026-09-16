from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from news.models import Source, SourceAccessInstruction


def card(source, status='approved', valid_until=None):
    return SourceAccessInstruction.objects.create(
        source=source, version=1, status=status, channel='rss',
        allowed_scope='metadata', endpoint='https://example.org/feed.xml',
        terms_url='https://example.org/terms', evidence={'proof': 'local'},
        reviewed_at=timezone.now(), reviewed_by='test', daily_request_cap=1,
        valid_until=valid_until or timezone.now() + timedelta(days=1),
    )


@pytest.mark.django_db
def test_preflight_accepts_only_active_configured_source_with_current_card(capsys):
    source = Source.objects.create(name='OK', url='https://example.org', source_type='rss')
    card(source)
    call_command('harvester_preflight')
    assert 'GOTOWE_DO_HARMONOGRAMU' in capsys.readouterr().out


@pytest.mark.django_db
def test_preflight_fails_for_active_source_with_expired_card(capsys):
    source = Source.objects.create(name='Expired', url='https://expired.example.org', source_type='rss')
    card(source, valid_until=timezone.now() - timedelta(seconds=1))
    with pytest.raises(SystemExit) as error:
        call_command('harvester_preflight')
    assert error.value.code == 2
    assert 'wygasła' in capsys.readouterr().out
