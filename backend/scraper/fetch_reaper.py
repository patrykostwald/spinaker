"""Close stale pre-network reservations without guessing their outcome."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from news.models import FetchAttempt, FetchRequest, SourceAccessInstruction
from scraper.utils import _record_transport_attempt


DEFAULT_MAX_AGE_SECONDS = 300
SUSPEND_AFTER_ABANDONED = 3


def reap_incomplete_fetches(*, max_age_seconds=DEFAULT_MAX_AGE_SECONDS, now=None):
    """Append an `abandoned` fact for expired open requests.

    The mutable FetchRequest row serializes this with the normal terminal write.
    The raw response is never recovered or reused; this records only that the
    result is unknown.
    """
    now = now or timezone.now()
    cutoff = now - timedelta(seconds=max_age_seconds)
    candidates = list(FetchRequest.objects.filter(
        state=FetchRequest.State.RESERVED, reserved_at__lte=cutoff,
    ).values_list('request_id', flat=True))
    reaped = suspended = 0
    for request_id in candidates:
        with transaction.atomic():
            request = FetchRequest.objects.select_for_update().select_related('source', 'instruction').filter(
                request_id=request_id).first()
            if request is None or request.state != FetchRequest.State.RESERVED or request.reserved_at > cutoff:
                continue
            reserved = FetchAttempt.objects.filter(
                request_id=request.request_id, outcome=FetchAttempt.Outcome.RESERVED,
            ).order_by('id').first()
            if reserved is None:
                continue
            _record_transport_attempt(source=request.source, instruction=request.instruction,
                requested_kind=reserved.requested_kind, url=f'https://{request.url_host}/',
                outcome=FetchAttempt.Outcome.ABANDONED, error_code='audit_incomplete',
                hostname_transport=reserved.transport == 'hostname_https', network_started=True,
                request_id=request.request_id, url_fingerprint_override=request.url_fingerprint)
            request.state = FetchRequest.State.ABANDONED
            request.closed_at = now
            request.save(update_fields=['state', 'closed_at'])
            reaped += 1
            recent = FetchAttempt.objects.filter(
                instruction=request.instruction, outcome=FetchAttempt.Outcome.ABANDONED,
                attempted_at__gte=now - timedelta(hours=1),
            ).count()
            if recent >= SUSPEND_AFTER_ABANDONED and request.instruction.status == SourceAccessInstruction.Status.APPROVED:
                request.instruction.status = SourceAccessInstruction.Status.SUSPENDED
                request.instruction.save(update_fields=['status'])
                suspended += 1
    return {'reaped': reaped, 'suspended': suspended}
