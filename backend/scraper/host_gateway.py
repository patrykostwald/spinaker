"""A database-backed, expiring per-host reservation.

The gateway is intentionally independent of transport and access decisions:
call it only after an instruction has passed the source gate and before a
network request.  PostgreSQL row locks make the update atomic across workers;
SQLite remains suitable only for one local worker.
"""
from dataclasses import dataclass
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from news.models import HostGate


@dataclass(frozen=True)
class AcquireResult:
    granted: bool
    retry_after_seconds: float = 0.0


class HostGateway:
    # Four bounded transport attempts can each spend 30 seconds reading.  A
    # crashed worker therefore releases automatically after 150 seconds, while
    # a normal completion releases the single-flight slot immediately and keeps
    # only the configured spacing after the request finishes.
    MAX_REQUEST_LEASE_SECONDS = 150

    def __init__(self, *, minimum_interval_seconds=3, now=timezone.now):
        self.minimum_interval_seconds = max(3, int(minimum_interval_seconds))
        self.now = now

    def acquire(self, host, worker_id):
        """Atomically reserve one host; a declined caller must not use network."""
        now = self.now()
        expiry = now + timedelta(seconds=self.MAX_REQUEST_LEASE_SECONDS)
        with transaction.atomic():
            try:
                # Savepoint keeps the outer transaction usable after a unique
                # conflict raised by simultaneous first reservations.
                with transaction.atomic():
                    HostGate.objects.create(host=host, locked_by=worker_id,
                        expires_at=expiry, next_allowed_at=now)
                return AcquireResult(True)
            except IntegrityError:
                gate = HostGate.objects.select_for_update().get(host=host)
                if gate.expires_at <= now and (gate.next_allowed_at is None or gate.next_allowed_at <= now):
                    gate.locked_by, gate.expires_at, gate.next_allowed_at = worker_id, expiry, now
                    gate.save(update_fields=['locked_by', 'expires_at', 'next_allowed_at'])
                    return AcquireResult(True)
                deadlines = [gate.expires_at]
                if gate.next_allowed_at is not None:
                    deadlines.append(gate.next_allowed_at)
                remaining = max(0.0, (max(deadlines) - now).total_seconds())
                return AcquireResult(False, remaining)

    def extend_on_429(self, host, worker_id, retry_after_seconds):
        """Extend only the caller's reservation; never shorten the existing TTL."""
        now = self.now()
        requested = now + timedelta(seconds=max(self.minimum_interval_seconds, int(retry_after_seconds)))
        with transaction.atomic():
            gate = HostGate.objects.select_for_update().filter(host=host).first()
            if gate is None or gate.locked_by != worker_id:
                return False
            if gate.next_allowed_at is None or requested > gate.next_allowed_at:
                gate.next_allowed_at = requested
                gate.save(update_fields=['next_allowed_at'])
            return True

    def complete(self, host, worker_id):
        """Release a completed request but preserve spacing from its finish."""
        now = self.now()
        minimum_next = now + timedelta(seconds=self.minimum_interval_seconds)
        with transaction.atomic():
            gate = HostGate.objects.select_for_update().filter(host=host).first()
            if gate is None or gate.locked_by != worker_id:
                return False
            gate.expires_at = now
            gate.next_allowed_at = max(gate.next_allowed_at or minimum_next, minimum_next)
            gate.save(update_fields=['expires_at', 'next_allowed_at'])
            return True

    def release(self, host, worker_id):
        """Backward-compatible name for completing a request."""
        return self.complete(host, worker_id)
