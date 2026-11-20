"""Klient HTTP do legislacja.rcl.gov.pl: jedyne miejsce, przez które zbieracz RCL wysyła zapytania.

Warunki zgody (pismo RCL.DPK.053.168.2026) egzekwuje scraper.rcl_guard na warstwie transportu; ten moduł dokłada:
odstęp 5 s (w tym przy kilku procesach: HostGate w bazie przez fetch_response_once), budżet zapytań na noc, robots.txt,
rozpoznanie odpowiedzi zapory (HTTP 200 "Request Rejected") i natychmiastowe wstrzymanie po 429/503 (oraz 403) do następnej nocy
bez ponawiania.  Każde zapytanie przechodzi przez audyt źródła (SourceAccessInstruction, FetchAttempt, dzienny limit karty).
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlsplit

import requests
from django.utils import timezone

from news.models import FetchAttempt
from scraper import rcl_guard
from scraper.access_gate import AccessDenied
from scraper.rcl_guard import RCL_BASE_URL, RCL_MIN_INTERVAL_SECONDS, RclRefused
from scraper.rcl_parser import is_rejected
from scraper.utils import HostRateLimited, fetch_response_once, retry_after_seconds


class RobotsPolicy:
    """robots.txt według RFC 9309: grupa dla naszego tokenu (inaczej `*`), znaki `*` i `$` w regułach, wygrywa najdłuższa reguła,
    a przy remisie Allow.  Biblioteka standardowa traktuje `*` w ścieżce dosłownie, więc `Disallow: /projekt/*/komentarz` nic by nie blokowało."""

    def __init__(self, lines):
        self.groups = []  # (agenci, reguły[(allow, wzorzec)])
        agents, rules, in_rules = [], [], False
        for raw in lines:
            line = raw.split('#', 1)[0].strip()
            if ':' not in line:
                continue
            key, value = (part.strip() for part in line.split(':', 1))
            key = key.lower()
            if key == 'user-agent':
                if in_rules:
                    self.groups.append((agents, rules))
                    agents, rules, in_rules = [], [], False
                agents.append(value.lower())
            elif key in ('allow', 'disallow') and agents:
                in_rules = True
                if value:
                    rules.append((key == 'allow', value))
        if agents:
            self.groups.append((agents, rules))

    @staticmethod
    def _matches(pattern, path):
        regex = re.escape(pattern).replace(r'\*', '.*')
        if regex.endswith(r'\$'):
            regex = regex[:-2] + '$'
        return re.match(regex, path) is not None

    def can_fetch(self, token, url):
        parts = urlsplit(url)
        path = parts.path or '/'
        if parts.query:
            path += '?' + parts.query
        token = token.lower()
        named = [rules for agents, rules in self.groups if any(a != '*' and a in token for a in agents)]
        rules = [r for group in (named or [g for agents, g in self.groups if '*' in agents]) for r in group]
        best = None  # (długość wzorca, allow)
        for allow, pattern in rules:
            if self._matches(pattern, path):
                candidate = (len(pattern), allow)
                if best is None or candidate[0] > best[0] or (candidate[0] == best[0] and allow):
                    best = candidate
        return best is None or best[1]


MAX_REDIRECTS = 2
HALT_STATUSES = (429, 503, 403)


class RclStop(Exception):
    """Koniec pobierania na tę noc (albo do odwołania); ``reason`` to stały kod do raportu."""

    def __init__(self, reason, detail=''):
        self.reason = reason
        self.detail = detail
        super().__init__(reason if not detail else f'{reason}: {detail}')


class RclTransient(Exception):
    """Pojedyncze zapytanie się nie powiodło (błąd sieci lub HTTP inny niż wstrzymujące); następne mogą iść."""


@dataclass(frozen=True)
class RclResponse:
    url: str
    status: int
    body: bytes
    fetched_at: object
    location: str = ''

    @property
    def text(self):
        return self.body.decode('utf-8', errors='replace')

    @property
    def sha256(self):
        return sha256(self.body).hexdigest()


def absolute_url(path_or_url):
    """Adres bezwzględny tylko na hoście RCL po https; inny host to błąd programisty, nie dane z sieci."""
    url = urljoin(RCL_BASE_URL + '/', path_or_url)
    parts = urlsplit(url)
    if parts.scheme != 'https' or not rcl_guard.is_rcl_url(url):
        raise ValueError('RCL client fetches only https://' + rcl_guard.RCL_HOST)
    return url.split('#')[0]


class RclClient:
    def __init__(self, source, instruction, *, request_budget=3000, sleep=time.sleep, monotonic=time.monotonic,
                 robots_override=False, deadline_seconds=None, dump_dir=None):
        self.source, self.instruction = source, instruction
        self.request_budget = int(request_budget)
        self.requests_made = 0
        self._sleep, self._monotonic = sleep, monotonic
        # Porcja zadania kończy się sama po deadline_seconds (zadanie Celery ma własne limity czasu).
        self._deadline = monotonic() + deadline_seconds if deadline_seconds else None
        self.dump_dir = Path(dump_dir) if dump_dir else None
        self._next_at = 0.0
        self._robots = None
        self.robots_override = robots_override
        self.robots_override_used = False

    # --- warunki przed każdym zapytaniem ---

    def _check(self, url):
        if self.requests_made >= self.request_budget:
            raise RclStop('budget', str(self.request_budget))
        if self._deadline is not None and self._monotonic() >= self._deadline:
            raise RclStop('slice_end')
        if self.instruction.minimum_interval_seconds < RCL_MIN_INTERVAL_SECONDS:
            raise RclStop('instruction_interval_below_minimum', str(self.instruction.minimum_interval_seconds))
        try:
            rcl_guard.guard_request(url)
        except RclRefused as exc:
            raise RclStop('window_closed' if exc.reason == 'outside_window' else exc.reason, exc.detail) from exc

    def _pace(self):
        wait = self._next_at - self._monotonic()
        if wait > 0:
            self._sleep(wait)

    # --- jedno zapytanie ---

    def _request(self, url, kind):
        """Jedno zapytanie przez audyt i bramki; zwraca RclResponse (także 3xx i 404), przerywa RclStop/RclTransient."""
        for _ in range(4):
            self._pace()
            self._check(url)
            try:
                response, _receipt = fetch_response_once(
                    url, audit_source=self.source, audit_instruction=self.instruction,
                    requested_kind=kind, hostname_transport=True)
            except HostRateLimited as exc:
                if exc.retry_after_seconds >= 3600:
                    raise RclStop('daily_cap') from exc
                if exc.retry_after_seconds > 60:
                    raise RclStop('host_gate_busy', f'{exc.retry_after_seconds:.0f}s') from exc
                self._sleep(exc.retry_after_seconds + 0.25)
                continue
            except AccessDenied as exc:
                raise RclStop('access_denied', str(exc)) from exc
            except RclRefused as exc:
                raise RclStop(exc.reason, exc.detail) from exc
            except requests.HTTPError as exc:
                self._after_request()
                status = getattr(exc.response, 'status_code', None)
                if status in HALT_STATUSES:
                    value = exc.response.headers.get('Retry-After', '') if exc.response is not None else ''
                    wait = retry_after_seconds(value) if value else 0
                    rcl_guard.halt(f'halt_{status}', status=status, url=url, retry_after_seconds=wait)
                    raise RclStop(f'halt_{status}') from exc
                if status in (404, 410):
                    return RclResponse(url, status, b'', timezone.now())
                raise RclTransient(f'http_{status}') from exc
            except (requests.RequestException, OSError, ValueError) as exc:
                self._after_request()
                raise RclTransient(f'{type(exc).__name__}:{str(exc)[:60]}') from exc
            self._after_request()
            fetched_at = timezone.now()
            if response.status_code == 200 and is_rejected(response.body[:8192]):
                rcl_guard.halt('waf_rejected', status=200, url=url)
                raise RclStop('waf_rejected')
            location = response.headers.get('Location', '') if response.status_code in (301, 302, 303, 307, 308) else ''
            return RclResponse(url, response.status_code, response.body, fetched_at, location)
        raise RclStop('host_gate_busy', 'retries')

    def _after_request(self):
        self.requests_made += 1
        self._next_at = self._monotonic() + RCL_MIN_INTERVAL_SECONDS + 0.1

    # --- robots.txt ---

    def robots(self):
        """Wczytuje robots.txt (jedno zapytanie na przebieg).  Brak pliku (404/410) oznacza brak ograniczeń."""
        if self._robots is None:
            url = absolute_url('/robots.txt')
            response = self._request(url, FetchAttempt.RequestedKind.ROBOTS)
            if response.status in (404, 410):
                lines = []
            elif response.status == 200:
                lines = response.text.splitlines()
            else:
                raise RclStop('robots_unavailable', str(response.status))
            self._robots = RobotsPolicy(lines)
        return self._robots

    def _robots_allow(self, url):
        if self.robots().can_fetch(rcl_guard.RCL_ROBOTS_TOKEN, url):
            return
        if self.robots_override:
            self.robots_override_used = True
            return
        raise RclStop('robots_disallowed', urlsplit(url).path)

    def _dump(self, response):
        """Tryb rozpoznania: surowa strona na dysk (poza repozytorium), do porównania z fixtures po pierwszej nocy."""
        if self.dump_dir is None or response.status != 200:
            return
        self.dump_dir.mkdir(parents=True, exist_ok=True)
        name = f'{self.requests_made:04d}_' + sha256(response.url.encode()).hexdigest()[:10] + '.html'
        (self.dump_dir / name).write_bytes(response.body)
        with (self.dump_dir / 'index.tsv').open('a', encoding='utf-8') as index:
            index.write('\t'.join((name, response.fetched_at.isoformat(), response.url)) + '\n')

    # --- publiczne ---

    def get(self, path_or_url, *, kind=FetchAttempt.RequestedKind.PAGE):
        """Strona RCL po https z obsługą co najwyżej dwóch przekierowań w obrębie hosta; każde to osobne zapytanie."""
        url = absolute_url(path_or_url)
        for _ in range(MAX_REDIRECTS + 1):
            self._robots_allow(url)
            response = self._request(url, kind)
            if not response.location:
                self._dump(response)
                return response
            url = absolute_url(response.location)
        raise RclTransient('too_many_redirects')
