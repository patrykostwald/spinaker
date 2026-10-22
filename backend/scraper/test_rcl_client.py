"""Klient RCL: odstęp 5 s, okno, User-Agent, przerwanie po 429/503, robots, zapora, flaga.  Cały transport podstawiony - bez sieci."""
from datetime import date, timezone as dt_timezone
import socket

from freezegun import freeze_time
import pytest
import requests

from news.models import FetchAttempt, ImportState, RclFetchEvent, SourceAccessInstruction
from scraper import rcl_guard, utils
from scraper.management.commands.configure_rcl_source import configure
from scraper.rcl_client import RclClient, RclStop, RclTransient, absolute_url
from scraper.rcl_guard import RCL_USER_AGENT
from scraper.rcl_testsupport import Clock, at, fixture_text, http_error, no_network, ok_response  # noqa: F401
from scraper.utils import HostRateLimited


def utc(moment):
    return moment.astimezone(dt_timezone.utc)


@pytest.fixture
def access(db):
    return configure('test')


@pytest.fixture(autouse=True)
def production_flag(monkeypatch):
    monkeypatch.setenv('RCL_FETCH_ENABLED', 'true')
    monkeypatch.delenv('RCL_ROBOTS_OVERRIDE', raising=False)


class Transport:
    """Podstawia fetch_response_once: zapisuje wywołania i oddaje zaplanowane odpowiedzi (lub wyjątki)."""

    def __init__(self, monkeypatch, clock=None):
        self.calls = []
        self.script = {}
        self.default = ok_response('<html><title>Projekt</title></html>')
        self.clock = clock
        monkeypatch.setattr('scraper.rcl_client.fetch_response_once', self)

    def __call__(self, url, *, audit_source, audit_instruction, requested_kind, hostname_transport=False, **kwargs):
        self.calls.append((url, requested_kind, self.clock.monotonic() if self.clock else None))
        outcome = self.script.get(url, self.default)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome, None


def make_client(access, clock, **kwargs):
    source, card = access
    return RclClient(source, card, sleep=clock.sleep, monotonic=clock.monotonic, **kwargs)


def robots_ok(transport, text='User-agent: *\nAllow: /\n'):
    transport.script['https://legislacja.rcl.gov.pl/robots.txt'] = ok_response(text)


def test_requests_are_spaced_by_at_least_five_seconds(access, monkeypatch, no_network):  # noqa: F811
    with freeze_time(utc(at(2))) as freezer:
        clock = Clock(freezer)
        transport = Transport(monkeypatch, clock)
        robots_ok(transport)
        client = make_client(access, clock)
        for page in range(4):
            client.get(f'/projekt/{page}')
    times = [call[2] for call in transport.calls]
    assert len(times) == 5  # robots.txt + 4 strony
    assert all(later - earlier >= 5 for earlier, later in zip(times, times[1:]))
    assert client.requests_made == 5 and not no_network


def test_global_five_second_gate_in_database_blocks_a_second_worker(access, monkeypatch):
    """Drugi proces (inny worker) nie przejdzie wcześniej niż po 5 s: HostGate w bazie, nie licznik w pamięci jednego procesu."""
    source, card = access
    monkeypatch.setattr(utils, '_fetch_feed_raw', lambda *a, **k: ok_response('<html>ok</html>'))
    url = 'https://legislacja.rcl.gov.pl/lista'
    kinds = FetchAttempt.RequestedKind
    with freeze_time(utc(at(2))) as freezer:
        utils.fetch_response_once(url, audit_source=source, audit_instruction=card, requested_kind=kinds.PAGE,
                                  hostname_transport=True)
        freezer.tick(2)
        with pytest.raises(HostRateLimited) as early:
            utils.fetch_response_once(url, audit_source=source, audit_instruction=card, requested_kind=kinds.PAGE,
                                      hostname_transport=True)
        assert 2.5 < early.value.retry_after_seconds <= 3.01
        freezer.tick(3.1)
        utils.fetch_response_once(url, audit_source=source, audit_instruction=card, requested_kind=kinds.PAGE,
                                  hostname_transport=True)


def test_host_gate_wait_is_slept_out_and_retried(access, monkeypatch):
    with freeze_time(utc(at(2))) as freezer:
        clock = Clock(freezer)
        transport = Transport(monkeypatch, clock)
        robots_ok(transport)
        real = transport.__call__
        state = {'first': True}

        def gated(url, **kwargs):
            if 'projekt' in url and state['first']:
                state['first'] = False
                raise HostRateLimited(2.0)
            return real(url, **kwargs)

        monkeypatch.setattr('scraper.rcl_client.fetch_response_once', gated)
        client = make_client(access, clock)
        assert client.get('/projekt/1').status == 200
    assert client.requests_made == 2  # robots + strona; odmowa bramki nie jest zapytaniem


def test_instruction_with_shorter_interval_is_refused_before_any_request(access, monkeypatch):
    source, card = access
    SourceAccessInstruction.objects.filter(pk=card.pk).update(minimum_interval_seconds=3)
    card.refresh_from_db()
    with freeze_time(utc(at(2))) as freezer:
        clock = Clock(freezer)
        transport = Transport(monkeypatch, clock)
        with pytest.raises(RclStop) as stop:
            make_client((source, card), clock).get('/lista')
    assert stop.value.reason == 'instruction_interval_below_minimum' and transport.calls == []


def test_flag_off_means_zero_requests(access, monkeypatch):
    monkeypatch.delenv('RCL_FETCH_ENABLED')
    with freeze_time(utc(at(2))) as freezer:
        clock = Clock(freezer)
        transport = Transport(monkeypatch, clock)
        with pytest.raises(RclStop) as stop:
            make_client(access, clock).get('/lista')
    assert stop.value.reason == 'disabled' and transport.calls == []


@pytest.mark.parametrize('moment', [at(0, 59, 59), at(6, 0, 0), at(12, 0), at(23, 59)])
def test_outside_the_window_zero_requests(access, monkeypatch, moment):
    with freeze_time(utc(moment)) as freezer:
        clock = Clock(freezer)
        transport = Transport(monkeypatch, clock)
        with pytest.raises(RclStop) as stop:
            make_client(access, clock).get('/lista')
    assert stop.value.reason == 'window_closed' and transport.calls == []


def test_first_request_at_exactly_one_and_stop_before_six(access, monkeypatch):
    with freeze_time(utc(at(1, 0, 0))) as freezer:
        clock = Clock(freezer)
        transport = Transport(monkeypatch, clock)
        robots_ok(transport)
        make_client(access, clock).get('/lista')
        assert len(transport.calls) == 2
    # noc kończy się przed 06:00: ostatnie zapytanie startuje najpóźniej 40 s przed końcem okna
    with freeze_time(utc(at(5, 58, 40))) as freezer:
        clock = Clock(freezer)
        transport = Transport(monkeypatch, clock)
        robots_ok(transport)
        client = make_client(access, clock)
        with pytest.raises(RclStop) as stop:
            for page in range(100):
                client.get(f'/projekt/{page}')
        assert stop.value.reason == 'window_closed'
    last_start_offset = transport.calls[-1][2] - 1000.0
    # robots o 05:58:40, potem co ~5,1 s; ostatnie wysłane zapytanie nie później niż 05:59:20
    assert last_start_offset <= 40.0
    assert len(transport.calls) <= 9


@pytest.mark.django_db
@pytest.mark.parametrize('status', [429, 503])
def test_429_and_503_stop_at_once_until_next_night_without_retry(access, monkeypatch, status):
    with freeze_time(utc(at(3))) as freezer:
        clock = Clock(freezer)
        transport = Transport(monkeypatch, clock)
        robots_ok(transport)
        transport.script['https://legislacja.rcl.gov.pl/projekt/7'] = http_error(status, {'Retry-After': '30'})
        client = make_client(access, clock)
        client.get('/projekt/6')
        with pytest.raises(RclStop) as stop:
            client.get('/projekt/7')
        assert stop.value.reason == f'halt_{status}'
        calls_after_halt = len(transport.calls)
        # żadnego ponowienia, także nowy klient (inny proces) tej samej nocy nie wysyła niczego
        with pytest.raises(RclStop) as again:
            make_client(access, clock).get('/projekt/8')
        assert again.value.reason == 'halted' and len(transport.calls) == calls_after_halt == 3
        assert rcl_guard.halted_until() == at(1, 0, day=date(2026, 10, 23))
    event = RclFetchEvent.objects.get(kind=f'halt_{status}')
    assert event.http_status == status and event.url == '/projekt/7'
    # od 01:00 następnej nocy wolno znów
    with freeze_time(utc(at(1, 0, 5, day=date(2026, 10, 23)))) as freezer:
        clock = Clock(freezer)
        transport = Transport(monkeypatch, clock)
        robots_ok(transport)
        assert make_client(access, clock).get('/projekt/9').status == 200


def test_403_and_waf_rejection_also_stop_the_night(access, monkeypatch):
    with freeze_time(utc(at(3))) as freezer:
        clock = Clock(freezer)
        transport = Transport(monkeypatch, clock)
        robots_ok(transport)
        transport.script['https://legislacja.rcl.gov.pl/projekt/1'] = ok_response(fixture_text('odrzucone_przez_zapore.html'))
        with pytest.raises(RclStop) as stop:
            make_client(access, clock).get('/projekt/1')
        assert stop.value.reason == 'waf_rejected'
    assert ImportState.objects.get(name='rcl:halt').cursor['reason'] == 'waf_rejected'
    ImportState.objects.all().delete()
    with freeze_time(utc(at(3))) as freezer:
        clock = Clock(freezer)
        transport = Transport(monkeypatch, clock)
        robots_ok(transport)
        transport.script['https://legislacja.rcl.gov.pl/projekt/2'] = http_error(403)
        with pytest.raises(RclStop) as stop:
            make_client(access, clock).get('/projekt/2')
        assert stop.value.reason == 'halt_403'


def test_404_and_server_errors_do_not_stop_the_night(access, monkeypatch):
    with freeze_time(utc(at(3))) as freezer:
        clock = Clock(freezer)
        transport = Transport(monkeypatch, clock)
        robots_ok(transport)
        transport.script['https://legislacja.rcl.gov.pl/projekt/1'] = http_error(404)
        transport.script['https://legislacja.rcl.gov.pl/projekt/2'] = http_error(500)
        transport.script['https://legislacja.rcl.gov.pl/projekt/3'] = requests.ConnectionError('boom')
        client = make_client(access, clock)
        assert client.get('/projekt/1').status == 404
        for number in (2, 3):
            with pytest.raises(RclTransient):
                client.get(f'/projekt/{number}')
        assert client.get('/projekt/4').status == 200
        assert rcl_guard.halted_until() is None


def test_budget_ends_the_run_with_a_clear_reason(access, monkeypatch):
    with freeze_time(utc(at(3))) as freezer:
        clock = Clock(freezer)
        transport = Transport(monkeypatch, clock)
        robots_ok(transport)
        client = make_client(access, clock, request_budget=3)
        client.get('/projekt/1')
        client.get('/projekt/2')
        with pytest.raises(RclStop) as stop:
            client.get('/projekt/3')
    assert stop.value.reason == 'budget' and len(transport.calls) == 3


def test_slice_deadline_ends_the_run(access, monkeypatch):
    with freeze_time(utc(at(3))) as freezer:
        clock = Clock(freezer)
        transport = Transport(monkeypatch, clock)
        robots_ok(transport)
        client = make_client(access, clock, deadline_seconds=12)
        with pytest.raises(RclStop) as stop:
            for page in range(10):
                client.get(f'/projekt/{page}')
    assert stop.value.reason == 'slice_end' and len(transport.calls) == 3


def test_robots_disallow_all_blocks_everything_after_the_single_robots_request(access, monkeypatch):
    with freeze_time(utc(at(3))) as freezer:
        clock = Clock(freezer)
        transport = Transport(monkeypatch, clock)
        robots_ok(transport, fixture_text('robots_disallow_all.txt'))
        client = make_client(access, clock)
        with pytest.raises(RclStop) as stop:
            client.get('/lista?typeId=2')
        assert stop.value.reason == 'robots_disallowed'
        with pytest.raises(RclStop):
            client.get('/projekt/1')
    assert [call[1] for call in transport.calls] == ['robots']


def test_robots_rule_for_our_agent_is_followed_and_override_is_explicit(access, monkeypatch):
    with freeze_time(utc(at(3))) as freezer:
        clock = Clock(freezer)
        transport = Transport(monkeypatch, clock)
        robots_ok(transport, fixture_text('robots_allow_iapply.txt'))
        client = make_client(access, clock)
        assert client.get('/projekt/1').status == 200
        with pytest.raises(RclStop):
            client.get('/projekt/1/komentarz')
        robots_ok(transport, fixture_text('robots_disallow_all.txt'))
        overridden = make_client(access, clock, robots_override=True)
        assert overridden.get('/projekt/1').status == 200 and overridden.robots_override_used


def test_only_https_rcl_host_can_be_requested():
    for url in ('http://legislacja.rcl.gov.pl/', 'https://evil.example/', 'https://rcl.gov.pl/', 'file:///etc/passwd'):
        with pytest.raises(ValueError):
            absolute_url(url)
    assert absolute_url('/lista?typeId=2#list') == 'https://legislacja.rcl.gov.pl/lista?typeId=2'


# --- transport: User-Agent i bramka przed połączeniem ---

class FakePool:
    sent = []

    def __init__(self, *args, **kwargs):
        pass

    def urlopen(self, method, url, headers=None, **kwargs):
        FakePool.sent.append((url, dict(headers)))

        class Response:
            status = 200
            headers = {}

            def stream(self, *a, **k):
                yield b'<html>ok</html>'

            def close(self):
                pass
        return Response()

    def close(self):
        pass

    clear = close


def test_transport_sends_exact_user_agent_to_rcl_and_the_old_one_elsewhere(monkeypatch):
    import urllib3
    FakePool.sent = []
    monkeypatch.setattr(urllib3, 'PoolManager', FakePool)
    monkeypatch.setattr(socket, 'getaddrinfo', lambda host, port, **kw: [(2, 1, 6, '', ('93.184.216.34', port))])
    monkeypatch.setattr(rcl_guard, 'halted_until', lambda now=None: None)
    with freeze_time(utc(at(3))):
        utils._fetch_feed_raw('https://legislacja.rcl.gov.pl/lista', hostname_transport=True)
        utils._fetch_feed_raw('https://example.org/feed', hostname_transport=True)
    rcl, other = FakePool.sent
    assert rcl[1]['User-Agent'] == 'iapply-legislacja/1.0 (+https://przeszlosc.today; kontakt@iapply.pl)'
    assert other[1]['User-Agent'] == utils.SOURCE_USER_AGENT


def test_transport_refuses_rcl_outside_window_before_resolving_dns(monkeypatch):
    import urllib3
    FakePool.sent = []
    resolved = []
    monkeypatch.setattr(urllib3, 'PoolManager', FakePool)
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: resolved.append(a) or [])
    with freeze_time(utc(at(12))):
        with pytest.raises(rcl_guard.RclRefused):
            utils._fetch_feed_raw('https://legislacja.rcl.gov.pl/lista', hostname_transport=True)
    monkeypatch.delenv('RCL_FETCH_ENABLED')
    with freeze_time(utc(at(3))):
        with pytest.raises(rcl_guard.RclRefused):
            utils._fetch_feed_raw('https://legislacja.rcl.gov.pl/lista', hostname_transport=True)
    assert resolved == [] and FakePool.sent == []


def test_audit_record_names_the_rcl_user_agent(access, monkeypatch):
    source, card = access
    monkeypatch.setattr(utils, '_fetch_feed_raw', lambda *a, **k: ok_response('<html>ok</html>'))
    with freeze_time(utc(at(3))):
        utils.fetch_response_once('https://legislacja.rcl.gov.pl/lista', audit_source=source, audit_instruction=card,
                                  requested_kind=FetchAttempt.RequestedKind.PAGE, hostname_transport=True)
    assert set(FetchAttempt.objects.values_list('request_user_agent', flat=True)) == {RCL_USER_AGENT}
