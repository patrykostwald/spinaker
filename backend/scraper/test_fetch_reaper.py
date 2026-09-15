from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from news.models import FetchAttempt, FetchRequest, Source, SourceAccessInstruction
from scraper.fetch_reaper import reap_incomplete_fetches
from scraper.utils import _close_fetch_request, _reserve_fetch_request


def approved_instruction(source):
    return SourceAccessInstruction.objects.create(
        source=source, version=1, status=SourceAccessInstruction.Status.APPROVED,
        channel=SourceAccessInstruction.Channel.RSS,
        allowed_scope=SourceAccessInstruction.Scope.METADATA,
        endpoint='https://example.org/feed', terms_url='https://example.org/terms',
        evidence={'basis': 'test'}, reviewed_at=timezone.now(), reviewed_by='test',
        valid_until=timezone.now() + timedelta(days=1),
    )


@pytest.mark.django_db
def test_reaper_closes_an_expired_reservation_without_claiming_fetch_result():
    source = Source.objects.create(name='Example', url='https://example.org')
    instruction = approved_instruction(source)
    request_id = uuid4()
    _reserve_fetch_request(source=source, instruction=instruction,
        requested_kind=FetchAttempt.RequestedKind.FEED, url=instruction.endpoint,
        hostname_transport=True, request_id=request_id)
    stale_at = timezone.now() - timedelta(minutes=6)
    FetchRequest.objects.filter(request_id=request_id).update(reserved_at=stale_at)
    FetchAttempt.objects.filter(request_id=request_id).update(attempted_at=stale_at)

    assert reap_incomplete_fetches(now=timezone.now()) == {'reaped': 1, 'suspended': 0}
    request = FetchRequest.objects.get(request_id=request_id)
    assert request.state == FetchRequest.State.ABANDONED
    assert list(FetchAttempt.objects.filter(request_id=request_id).values_list('outcome', flat=True)) == [
        FetchAttempt.Outcome.ABANDONED, FetchAttempt.Outcome.RESERVED,
    ]


@pytest.mark.django_db
def test_reaper_suspends_an_instruction_after_three_incomplete_attempts():
    source = Source.objects.create(name='Example', url='https://example.org')
    instruction = approved_instruction(source)
    stale_at = timezone.now() - timedelta(minutes=6)
    for _ in range(3):
        request_id = uuid4()
        _reserve_fetch_request(source=source, instruction=instruction,
            requested_kind=FetchAttempt.RequestedKind.FEED, url=instruction.endpoint,
            hostname_transport=True, request_id=request_id)
        FetchRequest.objects.filter(request_id=request_id).update(reserved_at=stale_at)
        FetchAttempt.objects.filter(request_id=request_id).update(attempted_at=stale_at)

    assert reap_incomplete_fetches(now=timezone.now()) == {'reaped': 3, 'suspended': 1}
    instruction.refresh_from_db()
    assert instruction.status == SourceAccessInstruction.Status.SUSPENDED


@pytest.mark.django_db
def test_two_incomplete_attempts_do_not_suspend_an_instruction():
    source = Source.objects.create(name='Example', url='https://example.org')
    instruction = approved_instruction(source)
    stale_at = timezone.now() - timedelta(minutes=6)
    for _ in range(2):
        _reserve_fetch_request(source=source, instruction=instruction,
            requested_kind=FetchAttempt.RequestedKind.FEED, url=instruction.endpoint,
            hostname_transport=True, request_id=uuid4())
    FetchRequest.objects.update(reserved_at=stale_at)

    assert reap_incomplete_fetches(now=timezone.now()) == {'reaped': 2, 'suspended': 0}
    instruction.refresh_from_db()
    assert instruction.status == SourceAccessInstruction.Status.APPROVED


@pytest.mark.django_db
def test_worker_cannot_close_a_request_already_closed_by_reaper():
    """The request row makes reaper-versus-worker resolution exactly one winner."""
    source = Source.objects.create(name='Example', url='https://example.org')
    instruction = approved_instruction(source)
    request_id = uuid4()
    _reserve_fetch_request(source=source, instruction=instruction,
        requested_kind=FetchAttempt.RequestedKind.FEED, url=instruction.endpoint,
        hostname_transport=True, request_id=request_id)
    stale_at = timezone.now() - timedelta(minutes=6)
    FetchRequest.objects.filter(request_id=request_id).update(reserved_at=stale_at)

    assert reap_incomplete_fetches(now=timezone.now()) == {'reaped': 1, 'suspended': 0}
    with pytest.raises(RuntimeError, match='no longer open'):
        _close_fetch_request(request_id=request_id, source=source, instruction=instruction,
            requested_kind=FetchAttempt.RequestedKind.FEED, url=instruction.endpoint,
            outcome=FetchAttempt.Outcome.OK, http_status=200, bytes_received=5,
            response_sha256='a' * 64, hostname_transport=True)

    assert list(FetchAttempt.objects.filter(request_id=request_id).values_list('outcome', flat=True)) == [
        FetchAttempt.Outcome.ABANDONED, FetchAttempt.Outcome.RESERVED,
    ]


@pytest.mark.django_db
def test_reservation_rolls_back_when_pre_network_receipt_cannot_be_saved(monkeypatch):
    """A network request can never follow a control row without its audit fact."""
    source = Source.objects.create(name='Example', url='https://example.org')
    instruction = approved_instruction(source)

    monkeypatch.setattr('scraper.utils._record_transport_attempt',
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError('audit storage unavailable')))

    with pytest.raises(RuntimeError, match='audit storage unavailable'):
        _reserve_fetch_request(source=source, instruction=instruction,
            requested_kind=FetchAttempt.RequestedKind.FEED, url=instruction.endpoint,
            hostname_transport=True, request_id=uuid4())

    assert FetchRequest.objects.count() == 0
    assert FetchAttempt.objects.count() == 0
