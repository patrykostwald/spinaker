"""Warunki zgody RCL zaszyte w kodzie: okno 01:00-06:00, User-Agent, flaga, wstrzymanie po 429/503.  Bez sieci."""
from datetime import date, timedelta, timezone as dt_timezone

from freezegun import freeze_time
import pytest
import requests

from news.models import ImportState, RclFetchEvent
from scraper import rcl_guard
from scraper.rcl_guard import RCL_USER_AGENT, RclRefused
from scraper.rcl_testsupport import at, no_network  # noqa: F401


def utc(moment):
    return moment.astimezone(dt_timezone.utc)


@pytest.mark.parametrize('moment, allowance, expected', [
    (at(0, 59, 59), 0, False),   # 00:59 - jeszcze nie
    (at(1, 0, 0), 0, True),      # 01:00 - tak
    (at(3, 30), 40, True),
    (at(5, 59, 0), 0, True),
    (at(5, 59, 59), 0, True),    # sama godzina w oknie, ale...
    (at(5, 59, 0), 40, True),    # zapytanie 40 s skończy się o 05:59:40
    (at(5, 59, 30), 40, False),  # ...a to mogłoby trwać po 06:00, więc nie startuje
    (at(6, 0, 0), 0, False),
    (at(12, 0), 0, False),
    (at(23, 59), 0, False),
])
def test_window_is_one_to_six_polish_time(moment, allowance, expected):
    assert rcl_guard.window_open(utc(moment), allowance_seconds=allowance) is expected


@pytest.mark.parametrize('day', [date(2026, 7, 15), date(2026, 12, 10), date(2026, 10, 24)])
def test_window_follows_polish_time_in_summer_and_winter(day):
    assert rcl_guard.window_open(utc(at(1, 0, day=day))) and not rcl_guard.window_open(utc(at(0, 59, 59, day=day)))
    assert not rcl_guard.window_open(utc(at(6, 0, day=day)))


def test_user_agent_is_exactly_the_one_in_the_letter():
    assert RCL_USER_AGENT == 'iapply-legislacja/1.0 (+https://przeszlosc.today; kontakt@iapply.pl)'
    assert rcl_guard.RCL_MIN_INTERVAL_SECONDS == 5


@pytest.mark.django_db
def test_guard_demands_every_condition(monkeypatch, no_network):  # noqa: F811
    url = 'https://legislacja.rcl.gov.pl/lista'
    monkeypatch.delenv('RCL_FETCH_ENABLED', raising=False)
    with freeze_time(utc(at(3))):
        with pytest.raises(RclRefused) as flag:
            rcl_guard.guard_request(url)
        assert flag.value.reason == 'disabled'
        monkeypatch.setenv('RCL_FETCH_ENABLED', 'true')
        assert rcl_guard.guard_request(url) == RCL_USER_AGENT
        with pytest.raises(RclRefused) as scheme:
            rcl_guard.guard_request('http://legislacja.rcl.gov.pl/lista')
        assert scheme.value.reason == 'not_https'
        # inne hosty nie podlegają warunkom RCL
        assert rcl_guard.guard_request('https://www.gov.pl/web/premier') is None
    with freeze_time(utc(at(12))):
        with pytest.raises(RclRefused) as window:
            rcl_guard.guard_request(url)
        assert window.value.reason == 'outside_window'
    assert not no_network


@pytest.mark.django_db
@pytest.mark.parametrize('status', [429, 503])
def test_halt_lasts_until_next_night_and_is_recorded(monkeypatch, status):
    monkeypatch.setenv('RCL_FETCH_ENABLED', 'true')
    url = 'https://legislacja.rcl.gov.pl/projekt/1'
    with freeze_time(utc(at(3, 15))):
        until = rcl_guard.halt(f'halt_{status}', status=status, url=url)
        assert until == at(1, 0, day=date(2026, 10, 23))
        with pytest.raises(RclRefused) as refused:
            rcl_guard.guard_request(url)
        assert refused.value.reason == 'halted'
    event = RclFetchEvent.objects.get()
    assert event.kind == f'halt_{status}' and event.http_status == status and event.url == '/projekt/1'
    # tej samej nocy później i następnego dnia przed 01:00 nadal wstrzymane; od 01:00 następnej nocy wolno
    with freeze_time(utc(at(5, 0))):
        with pytest.raises(RclRefused):
            rcl_guard.guard_request(url)
    with freeze_time(utc(at(0, 30, day=date(2026, 10, 23)))):
        assert rcl_guard.halted_until() is not None
    with freeze_time(utc(at(1, 0, 1, day=date(2026, 10, 23)))):
        assert rcl_guard.halted_until() is None
        assert rcl_guard.guard_request(url) == RCL_USER_AGENT


@pytest.mark.django_db
def test_halt_respects_a_longer_retry_after():
    with freeze_time(utc(at(3))):
        until = rcl_guard.halt('halt_429', status=429, url='/x', retry_after_seconds=3 * 86400)
    assert until - at(3) == timedelta(days=3)


def test_next_window_start_is_strictly_after_now():
    assert rcl_guard.next_window_start(utc(at(0, 30))) == at(1, 0)
    assert rcl_guard.next_window_start(utc(at(1, 0))) == at(1, 0, day=date(2026, 10, 23))
    assert rcl_guard.next_window_start(utc(at(23, 59))) == at(1, 0, day=date(2026, 10, 23))


@pytest.mark.django_db
def test_requests_library_is_guarded_too(monkeypatch, no_network):  # noqa: F811
    """Kod używający requests dostaje tę samą bramkę: bez flagi albo poza oknem nic nie wychodzi, w oknie dostaje własny User-Agent."""
    seen = []

    def fake_send(self, request, **kwargs):
        seen.append(request.headers['User-Agent'])
        response = requests.Response()
        response.status_code = 200
        response.url = request.url
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, 'send', fake_send)
    rcl_guard.install_requests_guard()
    monkeypatch.delenv('RCL_FETCH_ENABLED', raising=False)
    with freeze_time(utc(at(3))):
        with pytest.raises(RclRefused):
            requests.get('https://legislacja.rcl.gov.pl/lista', headers={'User-Agent': 'cokolwiek'})
        assert seen == []
        requests.get('https://example.org/', headers={'User-Agent': 'inny'})
        assert seen == ['inny']
        monkeypatch.setenv('RCL_FETCH_ENABLED', 'true')
        requests.get('https://legislacja.rcl.gov.pl/lista', headers={'User-Agent': 'cokolwiek'})
        assert seen[-1] == RCL_USER_AGENT
    with freeze_time(utc(at(12))):
        with pytest.raises(RclRefused):
            requests.get('https://legislacja.rcl.gov.pl/lista')
