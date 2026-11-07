"""Wspólne pomoce testów zbieracza RCL: blokada sieci, zegar sterowany z testu, fałszywy transport z plików."""
from datetime import date, datetime, timedelta
from pathlib import Path
import socket

import pytest
import requests
from zoneinfo import ZoneInfo

from scraper.utils import SourceHTTPResponse

FIXTURES = Path(__file__).parent / 'fixtures' / 'rcl'
WARSAW = ZoneInfo('Europe/Warsaw')
NIGHT = date(2026, 10, 22)


def fixture_text(name):
    return (FIXTURES / name).read_text(encoding='utf-8')


def at(hour, minute=0, second=0, day=NIGHT):
    """Chwila w czasie polskim jako aware datetime (testy nie zależą od strefy maszyny)."""
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=WARSAW)


@pytest.fixture
def no_network(monkeypatch):
    """Każda próba wyjścia w sieć kończy test porażką; ``attempts`` zlicza próby (powinno być 0)."""
    attempts = []

    def refuse(*args, **kwargs):
        attempts.append(args[1:2] or args[:1])
        raise AssertionError('Test próbował użyć sieci')

    monkeypatch.setattr(socket, 'getaddrinfo', refuse)
    monkeypatch.setattr(socket.socket, 'connect', refuse)
    monkeypatch.setattr(requests.adapters.HTTPAdapter, 'send', refuse)
    return attempts


class Clock:
    """Zegar testowy: freezegun dla czasu ściennego plus monotoniczny licznik dla odstępów klienta."""

    def __init__(self, freezer):
        self.freezer = freezer
        self.mono = 1000.0

    def monotonic(self):
        return self.mono

    def advance(self, seconds):
        self.mono += seconds
        self.freezer.tick(timedelta(seconds=seconds))

    sleep = advance


def ok_response(body, status=200, headers=None):
    body = body.encode('utf-8') if isinstance(body, str) else body
    return SourceHTTPResponse(status, headers or {}, body)


def http_error(status, headers=None):
    response = requests.Response()
    response.status_code = status
    response.headers.update(headers or {})
    return requests.HTTPError(f'HTTP {status}', response=response)
