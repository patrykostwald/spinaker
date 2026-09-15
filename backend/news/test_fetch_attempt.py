from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from news.models import FetchAttempt, Source, SourceAccessInstruction


def approved_instruction(source):
    return SourceAccessInstruction.objects.create(
        source=source,
        version=1,
        status=SourceAccessInstruction.Status.APPROVED,
        channel=SourceAccessInstruction.Channel.RSS,
        allowed_scope=SourceAccessInstruction.Scope.METADATA,
        endpoint='https://example.org/feed',
        terms_url='https://example.org/terms',
        evidence={'basis': 'test'},
        reviewed_at=timezone.now(),
        reviewed_by='test',
        valid_until=timezone.now() + timedelta(days=1),
    )


@pytest.mark.django_db
def test_fetch_attempt_records_a_success_and_cannot_change_or_delete():
    source = Source.objects.create(name='Example', url='https://example.org')
    instruction = approved_instruction(source)
    attempt = FetchAttempt.objects.create(
        source=source,
        instruction=instruction,
        instruction_version=instruction.version,
        channel=instruction.channel,
        requested_kind=FetchAttempt.RequestedKind.FEED,
        url_fingerprint='a' * 64,
        url_host='example.org',
        outcome=FetchAttempt.Outcome.OK,
        network_started=True,
        http_status=200,
        bytes_received=128,
        response_sha256='b' * 64,
    )

    assert attempt.pk
    attempt.outcome = FetchAttempt.Outcome.HTTP_ERROR
    with pytest.raises(ValidationError, match='append-only'):
        attempt.save()
    with pytest.raises(ValidationError, match='append-only'):
        attempt.delete()


@pytest.mark.django_db
def test_fetch_attempt_allows_a_pre_network_refusal_without_instruction():
    source = Source.objects.create(name='Example', url='https://example.org')

    attempt = FetchAttempt.objects.create(
        source=source,
        channel=SourceAccessInstruction.Channel.RSS,
        requested_kind=FetchAttempt.RequestedKind.FEED,
        url_fingerprint='a' * 64,
        url_host='example.org',
        outcome=FetchAttempt.Outcome.REFUSED_NO_INSTRUCTION,
        network_started=False,
        error_code='missing_instruction',
    )

    assert attempt.instruction is None


@pytest.mark.django_db
def test_fetch_attempt_rejects_a_success_without_matching_instruction():
    source = Source.objects.create(name='Example', url='https://example.org')

    with pytest.raises(ValidationError):
        FetchAttempt.objects.create(
            source=source,
            channel=SourceAccessInstruction.Channel.RSS,
            requested_kind=FetchAttempt.RequestedKind.FEED,
            url_fingerprint='a' * 64,
            url_host='example.org',
            outcome=FetchAttempt.Outcome.OK,
            network_started=True,
            http_status=200,
        )


@pytest.mark.django_db
def test_fetch_attempt_rejects_an_instruction_channel_mismatch():
    source = Source.objects.create(name='Example', url='https://example.org')
    instruction = approved_instruction(source)

    with pytest.raises(ValidationError):
        FetchAttempt.objects.create(
            source=source,
            instruction=instruction,
            instruction_version=instruction.version,
            channel=SourceAccessInstruction.Channel.HTML,
            requested_kind=FetchAttempt.RequestedKind.PAGE,
            url_fingerprint='a' * 64,
            url_host='example.org',
            outcome=FetchAttempt.Outcome.OK,
            network_started=True,
            http_status=200,
        )


@pytest.mark.django_db
def test_audited_feed_transport_records_success(monkeypatch):
    from scraper.utils import fetch_feed

    source = Source.objects.create(name='Example', url='https://example.org')
    instruction = approved_instruction(source)
    monkeypatch.setattr('scraper.utils._fetch_feed_raw', lambda *args, **kwargs: b'<rss/>')

    assert fetch_feed(
        instruction.endpoint,
        audit_source=source,
        audit_instruction=instruction,
        requested_kind=FetchAttempt.RequestedKind.FEED,
    ) == b'<rss/>'

    attempt = FetchAttempt.objects.get()
    assert attempt.outcome == FetchAttempt.Outcome.OK
    assert attempt.network_started is True
    assert attempt.bytes_received == len(b'<rss/>')
    assert attempt.adapter_revision == 'scraper.fetch_feed/v1'
    assert attempt.request_user_agent == 'ContextBeforeContent/1.0 source reader'


@pytest.mark.django_db
def test_official_api_uses_audited_transport(monkeypatch):
    from scraper.official import API, fetch_json, official_source

    source = official_source('sejm')
    SourceAccessInstruction.objects.create(
        source=source,
        version=1,
        status=SourceAccessInstruction.Status.APPROVED,
        channel=SourceAccessInstruction.Channel.API,
        allowed_scope=SourceAccessInstruction.Scope.METADATA,
        endpoint=API + '/sejm',
        terms_url=API + '/sejm.html',
        evidence={'basis': 'official API documentation'},
        reviewed_at=timezone.now(),
        reviewed_by='test',
        valid_until=timezone.now() + timedelta(days=1),
    )
    monkeypatch.setattr('scraper.utils._fetch_feed_raw', lambda *args, **kwargs: b'{"ok": true}')

    assert fetch_json('/sejm/term10/votings', offset=0) == {'ok': True}
    attempt = FetchAttempt.objects.get()
    assert attempt.channel == SourceAccessInstruction.Channel.API
    assert attempt.requested_kind == FetchAttempt.RequestedKind.API_RECORD
