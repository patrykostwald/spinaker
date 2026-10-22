"""Kolejka budowy (Z1): zatwierdzone bilety S/M -> GitHub Issues, idempotencja, zamknięcie, brak tokena, limit."""
import json
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command

from news import sprint_github as gh
from news.agent_models import BuildTicket
from news.models import RepairerState

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 13, 6, 20, tzinfo=ZoneInfo('Europe/Warsaw'))
TOKEN = 'github_pat_TESTTOKEN_abcdefghijklmnopqrstuvwxyz0123456789'


class Response:
    def __init__(self, status, payload=None, headers=None):
        self.status_code, self._payload, self.headers = status, payload, headers or {}

    def json(self):
        return self._payload


class FakeGitHub:
    """Pamięciowe repo: Issues, etykiety, PR; rejestruje każde żądanie (metoda, ścieżka, nagłówki)."""

    def __init__(self):
        self.issues, self.labels, self.pulls, self.calls, self.next = {}, set(), [], [], 100
        self.limit_after = None

    def __call__(self, method, url, headers=None, timeout=None, params=None, json=None, **kwargs):
        path = url.split('/repos/patrykostwald/spinaker', 1)[1]
        self.calls.append((method, path, headers or {}, json))
        if self.limit_after is not None and len([c for c in self.calls if c[0] != 'GET']) > self.limit_after and method != 'GET':
            return Response(403, {'message': 'rate limit'})
        if method == 'GET' and path == '/issues':
            rows = [i for i in self.issues.values() if i['state'] == 'open' and 'sprint' in i['labels']]
            return Response(200, rows)
        if method == 'GET' and path == '/pulls':
            return Response(200, self.pulls)
        if method == 'GET' and path.startswith('/labels/'):
            return Response(200 if path[8:] in self.labels else 404, {})
        if method == 'POST' and path == '/labels':
            self.labels.add(json['name'])
            return Response(201, json)
        if method == 'POST' and path == '/issues':
            self.next += 1
            issue = {'number': self.next, 'title': json['title'], 'body': json['body'], 'labels': json['labels'], 'state': 'open',
                     'html_url': f'https://github.com/patrykostwald/spinaker/issues/{self.next}'}
            self.issues[self.next] = issue
            return Response(201, issue)
        if method == 'POST' and path.endswith('/comments'):
            return Response(201, {})
        if method == 'PATCH' and path.startswith('/issues/'):
            self.issues[int(path.split('/')[2])]['state'] = json['state']
            return Response(200, {})
        raise AssertionError(f'nieoczekiwane żądanie {method} {path}')


@pytest.fixture
def github(monkeypatch):
    fake = FakeGitHub()
    monkeypatch.setenv('GITHUB_ISSUES_TOKEN', TOKEN)
    monkeypatch.setattr(gh, 'PAUSE', 0)
    with patch('requests.request', side_effect=fake), patch('django.utils.timezone.now', return_value=NOW):
        yield fake


def ticket(title, effort='S', status='approved', **fields):
    return BuildTicket.objects.create(title=title, effort=effort, status=status, brief='Zakres zlecenia', acceptance=['działa', 'testy'],
                                      due_date=NOW.date() + timedelta(days=3), **fields)


def test_export_creates_issues_for_approved_small_and_medium_only(github):
    small = ticket('Oś czasu wypowiedzi posła', 'S')
    big = ticket('Ślad pieniędzy v1', 'L')
    waiting = ticket('Czeka na decyzję', 'M', status='proposed')
    working = ticket('przeszłość.today: wyszukiwarka druków', 'M', status='in_progress', executor='codex')
    result = gh.export_issues(NOW)
    assert result['status'] == 'ok' and result['created'] == 2 and result['closed'] == 0 and result['open_issues'] == 2
    small.refresh_from_db(), big.refresh_from_db(), waiting.refresh_from_db(), working.refresh_from_db()
    assert small.issue_number and small.issue_url.endswith(f'/issues/{small.issue_number}')
    assert big.issue_number is None and waiting.issue_number is None and working.issue_number
    issue = github.issues[small.issue_number]
    assert issue['title'] == f'Sprint #{small.pk}: Oś czasu wypowiedzi posła'
    assert gh.MARKER.format(id=small.pk) in issue['body'] and 'Kryteria odbioru:' in issue['body'] and '- działa' in issue['body']
    assert f'sprint_zlecenia --zrobione {small.pk}' in issue['body'] and 'spin.clinic/panel' in issue['body']
    assert set(issue['labels']) == {'sprint', 'effort:S', 'executor:claude', 'area:spin.clinic'}
    assert set(github.issues[working.issue_number]['labels']) == {'sprint', 'effort:M', 'executor:codex', 'area:przeszlosc'}
    assert github.labels >= {'sprint', 'effort:S', 'effort:M', 'executor:claude', 'executor:codex', 'area:spin.clinic', 'area:przeszlosc'}
    # token tylko w nagłówku Authorization; nigdy w treści, tytule ani stanie
    assert all(h['Authorization'] == 'Bearer ' + TOKEN for _, _, h, _ in github.calls)
    assert TOKEN not in json.dumps([i for i in github.issues.values()]) and TOKEN not in json.dumps(RepairerState.objects.get(key=gh.STATE_KEY).data)
    assert TOKEN not in json.dumps(result)


def test_export_is_idempotent_and_adopts_existing_issue(github):
    first = ticket('Pierwszy bilet')
    gh.export_issues(NOW)
    creates = lambda: len([c for c in github.calls if c[0] == 'POST' and c[1] == '/issues'])  # noqa: E731
    assert creates() == 1
    # drugi bieg: nic nowego; etykiety już sprawdzone (bez kolejnych GET /labels)
    labels_before = len([c for c in github.calls if c[1].startswith('/labels')])
    gh.export_issues(NOW)
    assert creates() == 1 and len([c for c in github.calls if c[1].startswith('/labels')]) == labels_before
    # przerwany poprzedni bieg: Issue istnieje ze znacznikiem, a bilet nie ma numeru -> przyjęcie numeru zamiast duplikatu
    orphan = ticket('Bilet bez numeru')
    github.issues[777] = {'number': 777, 'title': 'x', 'body': gh.MARKER.format(id=orphan.pk), 'labels': ['sprint'], 'state': 'open',
                          'html_url': 'https://github.com/patrykostwald/spinaker/issues/777'}
    gh.export_issues(NOW)
    orphan.refresh_from_db()
    assert orphan.issue_number == 777 and creates() == 1
    assert first.pk != orphan.pk


def test_done_closes_issue_via_command_and_dropped_via_export(github):
    done = ticket('Zrobiony bilet')
    dropped = ticket('Odłożony bilet', 'M')
    gh.export_issues(NOW)
    out = StringIO()
    call_command('sprint_zlecenia', '--zrobione', str(done.pk), '--commit', 'abc1234', stdout=out)
    done.refresh_from_db()
    assert done.status == 'done' and done.issue_closed_at and github.issues[done.issue_number]['state'] == 'closed'
    assert f'Issue #{done.issue_number}: zamknięte.' in out.getvalue()
    comment = next(c for c in github.calls if c[1] == f'/issues/{done.issue_number}/comments')
    assert 'abc1234' in comment[3]['body']
    dropped.status = 'dropped'
    dropped.save(update_fields=['status'])
    result = gh.export_issues(NOW)
    dropped.refresh_from_db()
    assert result['closed'] == 1 and dropped.issue_closed_at and github.issues[dropped.issue_number]['state'] == 'closed'
    # zamknięte Issue nie zamyka się drugi raz
    patches = len([c for c in github.calls if c[0] == 'PATCH'])
    gh.export_issues(NOW)
    assert len([c for c in github.calls if c[0] == 'PATCH']) == patches


def test_without_token_everything_is_disabled(monkeypatch):
    monkeypatch.delenv('GITHUB_ISSUES_TOKEN', raising=False)
    row = ticket('Bez tokena')
    with patch('requests.request', side_effect=AssertionError('Bez sieci')):
        assert gh.export_issues(NOW) == {'status': 'disabled'}
        row.issue_number = 5
        assert gh.close_issue(row) is False
    assert 'wyłączona' in gh.report_line(NOW)
    out = StringIO()
    row.issue_number = None
    row.save()
    call_command('sprint_zlecenia', '--zrobione', str(row.pk), '--commit', 'abc1234', stdout=out)
    assert 'Issue' not in out.getvalue()


def test_rate_limit_stops_run_and_cap_per_run(github, monkeypatch):
    monkeypatch.setattr(gh, 'MAX_CREATE', 2)
    for n in range(3):
        ticket(f'Bilet {n}')
    result = gh.export_issues(NOW)
    assert result['created'] == 2 and BuildTicket.objects.filter(issue_number__isnull=True, status='approved').count() == 1
    github.limit_after = len([c for c in github.calls if c[0] != 'GET'])  # następny zapis = 403
    result = gh.export_issues(NOW)
    assert result['status'] in ('error', 'partial') and 'limit GitHub' in (result.get('error') or result.get('partial'))
    assert 'limit GitHub' in RepairerState.objects.get(key=gh.STATE_KEY).data['last_error']


def test_report_line_and_contract(github):
    github.pulls = [{'number': 1}, {'number': 2}]
    ticket('Jeden')
    gh.export_issues(NOW)
    line = gh.report_line(NOW)
    assert 'otwarte 1' in line and 'PR czekające 2' in line
    assert 'UWAGA' in gh.report_line(NOW + timedelta(hours=40))
    from news import raport_petli
    from news.daily_schedule import BEAT_PLAN
    assert raport_petli.BY_KEY['issues']['beats'] == ('sprint-export',) and BEAT_PLAN['sprint-export'] == ('sprint_export_task', {'hour': 6, 'minute': 20})
