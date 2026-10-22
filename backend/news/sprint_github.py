"""Kolejka budowy (Z1, przegląd architekta 7.10): zatwierdzony bilet sprintu S/M staje się Issue w GitHub.

export_issues(now) raz dziennie (6:20) i przy zamykaniu biletu (manage.py sprint_zlecenia --zrobione):
- bilet `approved`/`in_progress` bez numeru Issue dostaje Issue z treścią zlecenia (cel, zakres, kryteria odbioru,
  wysiłek, termin) i etykietami `sprint`, `effort:S|M`, `executor:codex|claude`, `area:spin.clinic|przeszlosc`;
- bilet `done` lub `dropped` z otwartym Issue zamyka je (komentarz z commitem);
- bilet L nie jest eksportowany (buduje go Claude w sesji; zostaje w skrócie Raportu pętli).
Idempotencja: przed utworzeniem czytamy otwarte Issues z etykietą `sprint` i dopasowujemy znacznik biletu w treści;
przerwany bieg nie tworzy duplikatu. Limit MAX_CREATE na bieg i pauza między zapisami; 403/429 kończy bieg.
Token GITHUB_ISSUES_TOKEN (fine-grained, tylko Issues RW jednego repo) nigdy nie trafia do logów ani stanu.
Bez tokena zadanie zwraca {'status': 'disabled'}. Rutyny chmurowej jeszcze nie ma (limit właściciela) - to tylko kolejka."""
import logging
import os
import re
import time
from datetime import timedelta

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

API = 'https://api.github.com'
DEFAULT_REPO = 'patrykostwald/spinaker'
MARKER = '<!-- sprint-ticket:{id} -->'
MARKER_RE = re.compile(r'<!-- sprint-ticket:(\d+) -->')
MAX_CREATE = 5
PAUSE = 1.0  # sekundy między zapisami (API GitHub: łagodny limit zapisów)
TIMEOUT = (5, 20)
STATE_KEY = 'sprint-github'
EXPORTED = ('S', 'M')
LABEL_COLORS = {'sprint': '0E8A16', 'effort:S': 'C2E0C6', 'effort:M': 'FBCA04', 'effort:L': 'D93F0B',
                'executor:codex': '5319E7', 'executor:claude': '1D76DB', 'area:spin.clinic': '0052CC', 'area:przeszlosc': '006B75',
                'fix': 'B60205'}
PANEL = 'https://spin.clinic/panel'


def token():
    return os.environ.get('GITHUB_ISSUES_TOKEN', '').strip()


def repo():
    return os.environ.get('GITHUB_ISSUES_REPO', DEFAULT_REPO).strip().strip('/') or DEFAULT_REPO


def enabled():
    return bool(token())


class RateLimited(Exception):
    """GitHub odpowiedział 403/429 (limit): kończymy bieg, reszta w następnym."""


class Client:
    """Minimalny klient REST; nagłówki budowane przy każdym żądaniu, token nie jest zapisywany w obiekcie."""

    def __init__(self, repository=None):
        self.repo = repository or repo()
        self.writes = 0

    def _headers(self):
        return {'Authorization': 'Bearer ' + token(), 'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'spin-clinic-sprint'}

    def request(self, method, path, **kwargs):
        response = requests.request(method, f'{API}/repos/{self.repo}{path}', headers=self._headers(), timeout=TIMEOUT, **kwargs)
        if response.status_code in (403, 429):
            raise RateLimited(f'HTTP {response.status_code}')
        if response.status_code >= 400 and response.status_code != 404:
            raise requests.HTTPError(f'GitHub HTTP {response.status_code} ({method} {path})')
        if method != 'GET':
            self.writes += 1
            if PAUSE:
                time.sleep(PAUSE)
        return response

    def open_sprint_issues(self):
        out = []
        page = 1
        while page <= 5:
            response = self.request('GET', '/issues', params={'labels': 'sprint', 'state': 'open', 'per_page': 100, 'page': page})
            rows = response.json() if response.status_code == 200 else []
            out += [r for r in rows if isinstance(r, dict) and 'pull_request' not in r]
            if len(rows) < 100:
                break
            page += 1
        return out

    def open_pull_requests(self):
        response = self.request('GET', '/pulls', params={'state': 'open', 'per_page': 100})
        return len(response.json()) if response.status_code == 200 else 0

    def ensure_label(self, name):
        if self.request('GET', f'/labels/{name}').status_code == 404:
            self.request('POST', '/labels', json={'name': name, 'color': LABEL_COLORS.get(name, 'EDEDED')})

    def create_issue(self, title, body, labels):
        response = self.request('POST', '/issues', json={'title': title, 'body': body, 'labels': labels})
        return response.json()

    def close_issue(self, number, comment):
        if comment:
            self.request('POST', f'/issues/{number}/comments', json={'body': comment})
        self.request('PATCH', f'/issues/{number}', json={'state': 'closed', 'state_reason': 'completed'})


def area(ticket):
    text = (ticket.title or '').lower()
    agent = ticket.note.agent if ticket.note else ''
    return 'area:przeszlosc' if text.startswith('przeszłość.today') or agent in ('kartograf', 'zwiadowca', 'wynalazca', 'technolog', 'architekt') \
        else 'area:spin.clinic'


def labels(ticket):
    out = ['sprint', f'effort:{ticket.effort}', f'executor:{ticket.executor}', area(ticket)]
    if getattr(ticket, 'kind', '') == 'fix':
        out.append('fix')
    return out


def title(ticket):
    return f'Sprint #{ticket.pk}: {ticket.title}'[:240]


def body(ticket):
    from news import sprint
    lines = [MARKER.format(id=ticket.pk), '', sprint.brief(ticket), '',
             f'Wysiłek: {ticket.effort} · wykonawca: {ticket.executor} · ranking: {ticket.rank:g}',
             f'Panel decyzji: {PANEL} (karta „Sprint tygodnia”, bilet #{ticket.pk})', '',
             'Zasady rutyny: gałąź `sprint/' + str(ticket.pk) + '`, testy offline, zrzuty 1440/390 w PR, bez czytania .env, '
             'bez zmian w clinic_council.py i council_quorum.py bez etykiety `konsylium`. PR scala tylko Claude po przeglądzie.']
    return '\n'.join(lines)


def _state():
    from news.models import RepairerState
    row, _ = RepairerState.objects.get_or_create(key=STATE_KEY)
    return row


def _save(row, **data):
    row.data = {**(row.data or {}), **data}
    row.save(update_fields=['data'])


def _existing_by_ticket(client):
    out = {}
    for issue in client.open_sprint_issues():
        match = MARKER_RE.search(issue.get('body') or '')
        if match:
            out[int(match.group(1))] = issue
    return out


def export_issues(now=None, client=None):
    """Tworzy Issues dla zatwierdzonych biletów S/M i zamyka Issues biletów zamkniętych. Zwraca podsumowanie bez tokena."""
    from news.agent_models import BuildTicket
    if not enabled():
        return {'status': 'disabled'}
    now = now or timezone.now()
    client = client or Client()
    created, closed, errors = [], [], []
    row = _state()
    try:
        existing = _existing_by_ticket(client)
        to_create = list(BuildTicket.objects.select_related('note').filter(status__in=('approved', 'in_progress'), effort__in=EXPORTED,
                                                                            issue_number__isnull=True).order_by('due_date', '-rank', 'pk'))
        ensured = set((row.data or {}).get('labels') or [])
        for ticket in to_create:
            issue = existing.get(ticket.pk)
            if not issue:
                if len(created) >= MAX_CREATE:
                    break
                for name in labels(ticket):
                    if name not in ensured:
                        client.ensure_label(name)
                        ensured.add(name)
                issue = client.create_issue(title(ticket), body(ticket), labels(ticket))
            ticket.issue_number, ticket.issue_url = int(issue['number']), str(issue.get('html_url') or '')[:200]
            ticket.save(update_fields=['issue_number', 'issue_url'])
            created.append(ticket.pk)
        _save(row, labels=sorted(ensured))
        for ticket in BuildTicket.objects.filter(status__in=('done', 'dropped'), issue_number__isnull=False, issue_closed_at__isnull=True):
            close_issue(ticket, now, client)
            closed.append(ticket.pk)
        open_count = len(existing) + len([pk for pk in created if pk not in existing]) - len(closed)
        pulls = client.open_pull_requests()
        _save(row, checked_at=now.isoformat(), open_issues=max(0, open_count), open_pulls=pulls, last_error='')
    except RateLimited as error:
        errors.append(f'limit GitHub: {error}')
        _save(row, checked_at=now.isoformat(), last_error=errors[-1])
    except (requests.RequestException, ValueError, KeyError) as error:
        errors.append(type(error).__name__)
        _save(row, checked_at=now.isoformat(), last_error=errors[-1])
    status = 'ok' if not errors else 'partial' if (created or closed) else 'error'
    result = {'status': status, 'created': len(created), 'closed': len(closed), 'produced': len(created) + len(closed),
              'open_issues': (row.data or {}).get('open_issues', 0), 'open_pulls': (row.data or {}).get('open_pulls', 0)}
    if errors:
        result['partial' if status == 'partial' else 'error'] = '; '.join(errors)[:200]
    return result


def close_issue(ticket, now=None, client=None):
    """Zamyka Issue biletu (po --zrobione albo „Nie teraz”). Bez tokena lub bez numeru: nic. Błąd sieci nie zatrzymuje biletu."""
    if not enabled() or not ticket.issue_number or ticket.issue_closed_at:
        return False
    now = now or timezone.now()
    client = client or Client()
    comment = (f'Zrobione: commit `{ticket.commit}` ({now.astimezone(timezone.get_current_timezone()):%d.%m.%Y}).' if ticket.status == 'done' and ticket.commit
               else 'Bilet odłożony przez właściciela („Nie teraz”).' if ticket.status == 'dropped' else '')
    try:
        client.close_issue(ticket.issue_number, comment)
    except (RateLimited, requests.RequestException, ValueError) as error:
        logger.warning('sprint_github close #%s: %s', ticket.pk, type(error).__name__)
        return False
    ticket.issue_closed_at = now
    ticket.save(update_fields=['issue_closed_at'])
    return True


def snapshot():
    from news.models import RepairerState
    row = RepairerState.objects.filter(key=STATE_KEY).first()
    return dict(row.data or {}) if row else {}


def report_line(now=None):
    """Linia do sekcji „Sprint tygodnia” Raportu pętli: Issues otwarte, PR czekające, ostatnia kontrola."""
    if not enabled():
        return 'Kolejka budowy (GitHub Issues): wyłączona - brak GITHUB_ISSUES_TOKEN.'
    data = snapshot()
    if not data.get('checked_at'):
        return 'Kolejka budowy (GitHub Issues): jeszcze nie eksportowano (pierwszy bieg 6:20).'
    from news.repairer import stamp
    at = stamp(data['checked_at'])
    when = at.astimezone(timezone.get_current_timezone()).strftime('%d.%m %H:%M') if at else '?'
    line = f"Kolejka budowy (GitHub Issues): otwarte {data.get('open_issues', 0)}, PR czekające {data.get('open_pulls', 0)} (stan {when})"
    if data.get('last_error'):
        line += f"; ostatni błąd: {data['last_error']}"
    if at and now and now - at > timedelta(hours=36):
        line += '; UWAGA: eksport nie działał od ponad 36 h'
    return line
