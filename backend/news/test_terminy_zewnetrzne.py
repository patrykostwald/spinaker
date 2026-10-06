"""Terminy zewnętrzne i puls z zewnątrz (Z3): parser RDAP, progi, brak klucza = na, maile raz na próg, Dyżurny, ping."""
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from news import puls_zewnetrzny as puls, terminy_zewnetrzne as tz
from news.models import RepairerState

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 7, 6, 15, tzinfo=ZoneInfo('Europe/Warsaw'))
RDAP_SAMPLE = {'objectClassName': 'domain', 'ldhName': 'spin.clinic', 'status': ['active', 'client transfer prohibited'],
               'events': [{'eventAction': 'registration', 'eventDate': '2026-09-13T10:00:00Z'},
                          {'eventAction': 'expiration', 'eventDate': '2027-09-13T10:00:00Z'}]}


class Ctx:
    def __init__(self, now):
        self.now = now


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    for name in ('OPENROUTER_API_KEY', 'X_POLITICAL_BEARER_TOKEN', 'GITHUB_ISSUES_TOKEN', 'GITHUB_ISSUES_TOKEN_CREATED', 'HEALTHCHECK_URL',
                 'HEALTHCHECK_PING_URL'):
        monkeypatch.delenv(name, raising=False)
    with patch('django.utils.timezone.now', return_value=NOW), patch('requests.get', side_effect=AssertionError('Bez sieci')), \
         patch('requests.post', side_effect=AssertionError('Bez sieci')), patch('requests.request', side_effect=AssertionError('Bez sieci')):
        yield


def probes(monkeypatch, domain_days=300, tls_days=60, ips=('148.113.242.109',), bad=False, credits=None, usage=None):
    expires = NOW + timedelta(days=domain_days)
    monkeypatch.setattr(tz, 'rdap', lambda d: {'expires': expires, 'status': ['client hold'] if bad else ['active']})
    monkeypatch.setattr(tz, 'tls_expiry', lambda h: NOW + timedelta(days=tls_days))
    monkeypatch.setattr(tz, 'dns_a', lambda h: list(ips))
    monkeypatch.setattr(tz, 'openrouter_credits', lambda: credits)
    monkeypatch.setattr(tz, 'x_usage', lambda: usage)


def by_key(items):
    return {it['key']: it for it in items}


def test_parse_rdap_and_thresholds():
    info = tz.parse_rdap(RDAP_SAMPLE)
    assert info['expires'] == datetime(2027, 9, 13, 10, tzinfo=dt_timezone.utc) and info['status'] == ['active', 'client transfer prohibited']
    assert tz.parse_rdap({'events': [], 'status': ['pendingDelete']}) == {'expires': None, 'status': ['pendingdelete']}
    assert tz.days_left(info['expires'], NOW) == 341
    assert [tz.stage(d) for d in (None, 60, 30, 20, 14, 5, 3, 0)] == [None, None, 30, 30, 14, 14, 3, 3]
    assert [tz.level_for(d) for d in (None, 60, 30, 14, 3, 0)] == ['ok', 'ok', 'warning', 'warning', 'critical', 'critical']
    assert tz.level_for(300, bad=True) == 'critical'


def test_collect_levels_and_missing_keys(monkeypatch):
    probes(monkeypatch, domain_days=10, tls_days=5, ips=('1.2.3.4',))
    items, _ = tz.collect(NOW, {})
    found = by_key(items)
    assert found['domena:spin.clinic']['level'] == 'warning' and found['domena:spin.clinic']['days'] == 10
    assert found['tls:spin.clinic']['level'] == 'warning' and found['tls:spin.clinic']['days'] == 5
    assert found['dns:spin.clinic']['level'] == 'critical' and '148.113.242.109' in found['dns:spin.clinic']['detail']
    assert 'dns:zbudujmi.com' not in found and found['saldo:openrouter']['level'] == 'na' and found['saldo:x']['level'] == 'na'
    assert found['token:github']['level'] == 'na' and found['manual:Gemini']['level'] == 'manual'
    assert {it['label'] for it in items if it['kind'] == 'domena'} == set(tz.DOMAINS)


def test_bad_status_balances_and_github_token(monkeypatch):
    probes(monkeypatch, bad=True, credits=1.5, usage={'used': 90, 'cap': 100, 'pct': 90, 'reset_day': 12})
    monkeypatch.setenv('GITHUB_ISSUES_TOKEN', 'github_pat_abc')
    monkeypatch.setenv('GITHUB_ISSUES_TOKEN_CREATED', (NOW - timedelta(days=80)).date().isoformat())
    found = by_key(tz.collect(NOW, {})[0])
    assert found['domena:iapply.pl']['level'] == 'critical' and 'client hold' in found['domena:iapply.pl']['detail']
    assert found['saldo:openrouter']['level'] == 'warning' and 'openrouter.ai/settings/credits' in found['saldo:openrouter']['instruction']
    assert found['saldo:x']['level'] == 'warning' and '90%' in found['saldo:x']['detail']
    assert found['token:github']['level'] == 'warning' and found['token:github']['days'] == 10
    # bez daty w .env: pierwsze zauważenie tokena liczy się jako data utworzenia (i zmienia się przy nowym tokenie)
    monkeypatch.delenv('GITHUB_ISSUES_TOKEN_CREATED')
    items, data = tz.collect(NOW, {})
    assert by_key(items)['token:github']['days'] == 90 and data['github_token_seen'] == NOW.isoformat()
    monkeypatch.setenv('GITHUB_ISSUES_TOKEN', 'github_pat_nowy')
    _, data2 = tz.collect(NOW + timedelta(days=5), data)
    assert data2['github_token_hash'] != data['github_token_hash'] and data2['github_token_seen'] != data['github_token_seen']


def test_probe_failure_is_unknown_not_alarm(monkeypatch):
    probes(monkeypatch)

    def boom(d):
        raise RuntimeError('RDAP HTTP 503')
    monkeypatch.setattr(tz, 'rdap', boom)
    found = by_key(tz.collect(NOW, {})[0])
    assert found['domena:spin.clinic']['level'] == 'unknown' and 'RuntimeError' in found['domena:spin.clinic']['detail']
    assert found['tls:spin.clinic']['level'] == 'ok'


def test_run_mails_once_per_threshold_and_duty_reads_state(monkeypatch):
    sent = []
    monkeypatch.setattr(tz, '_mail', lambda subject, body: sent.append((subject, body)) or True)
    probes(monkeypatch, domain_days=20)
    result = tz.run(NOW)
    assert result['status'] == 'ok' and result['warning'] == 4 and result['mails'] == 4 and len(sent) == 1
    assert 'Terminy zewnętrzne: uwaga' in sent[0][0] and 'Odnów domenę spin.clinic' in sent[0][1]
    assert tz.run(NOW)['mails'] == 0 and len(sent) == 1  # ten sam próg: bez drugiego maila
    probes(monkeypatch, domain_days=2)
    assert tz.run(NOW)['critical'] == 4 and len(sent) == 2 and 'KRYTYCZNY' in sent[1][0]
    alarms = {a['key']: a for a in tz.check_terminy(Ctx(NOW))}
    assert alarms['terminy:domena:spin.clinic']['severity'] == 'critical' and 'Odnów domenę' in alarms['terminy:domena:spin.clinic']['instruction']
    assert 'terminy:tls:spin.clinic' not in alarms and 'terminy:stale' not in alarms
    probes(monkeypatch, domain_days=300)
    tz.run(NOW)
    assert tz.check_terminy(Ctx(NOW)) == [] and RepairerState.objects.get(key=tz.STATE_KEY).data['mailed'] == {}
    stale = {a['key'] for a in tz.check_terminy(Ctx(NOW + timedelta(days=3)))}
    assert stale == {'terminy:stale'}


def test_report_lines_and_table(monkeypatch):
    assert tz.report_lines(NOW)[0].startswith('Terminy zewnętrzne: jeszcze nie sprawdzono')
    probes(monkeypatch, domain_days=341, credits=12.5)
    monkeypatch.setattr(tz, '_mail', lambda *a: True)
    tz.run(NOW)
    lines = tz.report_lines(NOW)
    assert lines[0] == 'Terminy zewnętrzne (stan 07.10 06:15):'
    spin = next(l for l in lines if l.startswith('- spin.clinic:'))
    assert '(341 dni)' in spin and 'TLS do' in spin and 'DNS A -> 148.113.242.109' in spin
    assert any('OpenRouter: kredyty 12.50 USD' in l for l in lines) and any('Ręcznie raz w miesiącu' in l for l in lines)
    assert 'spin.clinic' in tz.table(NOW)
    from news import duty, duty_extra, raport_petli
    assert tz.check_terminy in duty_extra.CHECKS and tz.check_terminy in duty.CHECKS
    report = raport_petli.build(NOW)
    assert report['zewnetrzne']['terminy'] == lines and '== Kopia, puls i terminy zewnętrzne ==' in raport_petli.text(report)


# --- puls z zewnątrz -----------------------------------------------------------------------------------------------

def test_pulse_disabled_without_url():
    assert puls.run(NOW) == {'status': 'disabled'} and 'wyłączony' in puls.report_line(NOW)


def test_pulse_pings_only_when_duty_is_fresh(monkeypatch):
    monkeypatch.setenv('HEALTHCHECK_URL', 'https://hc-ping.com/abc/')
    calls = []

    def get(url, timeout=None):
        calls.append(('GET', url, ''))
        return type('R', (), {'status_code': 200})()

    def post(url, data=b'', timeout=None):
        calls.append(('POST', url, data.decode()))
        return type('R', (), {'status_code': 200})()
    with patch('requests.get', side_effect=get), patch('requests.post', side_effect=post):
        result = puls.run(NOW)
        assert result['status'] == 'error' and 'brak jakiegokolwiek pulsu' in result['error']
        assert [c[1] for c in calls] == ['https://hc-ping.com/abc/start', 'https://hc-ping.com/abc/fail'] and 'Dyżurny' in calls[1][2]
        RepairerState.objects.create(key='pulse:duty-15m', data={'result': 'ok', 'last_event': (NOW - timedelta(minutes=4)).isoformat()})
        calls.clear()
        result = puls.run(NOW)
        assert result == {'status': 'ok', 'produced': 1, 'delivered': True}
        assert [c[1] for c in calls] == ['https://hc-ping.com/abc/start', 'https://hc-ping.com/abc']
        assert puls.report_line(NOW) == 'Puls z zewnątrz: ostatni ping 06:15 ok'
        RepairerState.objects.filter(key='pulse:duty-15m').update(data={'result': 'ok', 'last_event': (NOW - timedelta(minutes=20)).isoformat()})
        assert '20 min temu' in puls.run(NOW)['error']
        RepairerState.objects.filter(key='pulse:duty-15m').update(data={'result': 'error', 'consecutive_errors': 3, 'last_event': NOW.isoformat()})
        assert '3 z rzędu' in puls.run(NOW)['error'] and 'FAIL' in puls.report_line(NOW)
    assert 'UWAGA' in puls.report_line(NOW + timedelta(minutes=30))
    from news import raport_petli
    from news.daily_schedule import BEAT_PLAN
    assert BEAT_PLAN['puls-zewnetrzny-5m'] == ('puls_zewnetrzny_task', {'minute': '2-59/5'}) and raport_petli.BY_KEY['puls']['registry'] == 'puls-zewnetrzny'
