from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from scraper.host_gateway import HostGateway


class Clock:
    def __init__(self):
        self.value = datetime(2026, 9, 15, tzinfo=dt_timezone.utc)

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


@pytest.mark.django_db
def test_one_host_is_reserved_for_the_full_minimum_interval():
    clock = Clock()
    gateway = HostGateway(now=clock)

    assert gateway.acquire('example.org', 'a').granted
    assert not gateway.acquire('example.org', 'b').granted
    gateway.release('example.org', 'a')
    clock.advance(2.9)
    assert not gateway.acquire('example.org', 'b').granted
    clock.advance(0.1)
    assert gateway.acquire('example.org', 'b').granted


@pytest.mark.django_db
def test_two_hosts_do_not_block_each_other():
    gateway = HostGateway(now=Clock())

    assert gateway.acquire('one.example', 'a').granted
    assert gateway.acquire('two.example', 'b').granted


@pytest.mark.django_db
def test_only_lock_owner_can_extend_after_429():
    clock = Clock()
    gateway = HostGateway(now=clock)

    assert gateway.acquire('example.org', 'a').granted
    assert not gateway.extend_on_429('example.org', 'b', 60)
    assert gateway.extend_on_429('example.org', 'a', 60)
    gateway.complete('example.org', 'a')
    clock.advance(10)
    result = gateway.acquire('example.org', 'b')
    assert not result.granted
    assert result.retry_after_seconds == pytest.approx(50)


@pytest.mark.django_db
def test_an_expired_worker_reservation_recovers_without_release():
    clock = Clock()
    gateway = HostGateway(now=clock)

    assert gateway.acquire('example.org', 'crashed-worker').granted
    clock.advance(HostGateway.MAX_REQUEST_LEASE_SECONDS)
    assert gateway.acquire('example.org', 'replacement').granted


@pytest.mark.django_db
def test_active_request_cannot_be_overtaken_after_the_minimum_interval():
    clock = Clock()
    gateway = HostGateway(now=clock)

    assert gateway.acquire('example.org', 'slow-worker').granted
    clock.advance(10)
    assert not gateway.acquire('example.org', 'second-worker').granted
    gateway.complete('example.org', 'slow-worker')
    clock.advance(2.9)
    assert not gateway.acquire('example.org', 'second-worker').granted
    clock.advance(0.1)
    assert gateway.acquire('example.org', 'second-worker').granted
