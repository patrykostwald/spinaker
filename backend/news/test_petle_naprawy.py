"""Naprawy automatyczne pętli (właściciel 6.10): naprawa przed alarmem, limity prób, dziennik, nigdy nie usuwa,
nigdy nie publikuje raportów Raportysty."""
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.core.cache import cache

from news import petle_bezpieczniki as fuses, petle_naprawy as fix, raport_petli, sprint
from news.agent_models import AgentNote, BuildTicket, SebaReview
from news.models import RepairAction, RepairerState

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 6, 12, tzinfo=ZoneInfo('Europe/Warsaw'))


class Ctx:
    def __init__(self, now):
        self.now = now


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    cache.clear()
    monkeypatch.setenv('AGENTS_ENABLED', 'true')
    monkeypatch.setenv('SEBA_ENABLED', 'false')
    monkeypatch.delenv('LOOP_AUTOREPAIR', raising=False)
    with patch('django.utils.timezone.now', return_value=NOW), \
         patch('requests.post', side_effect=AssertionError('Bez sieci')), \
         patch('requests.get', side_effect=AssertionError('Bez sieci')), \
         patch('config.celery.app.send_task') as send:
        yield send
    cache.clear()


def note(agent, kind='idea', days=0, **fields):
    row = AgentNote.objects.create(agent=agent, kind=kind, title=fields.pop('title', f'{agent} {kind} {AgentNote.objects.count()}'),
                                   body='b', **fields)
    AgentNote.objects.filter(pk=row.pk).update(created_at=NOW - timedelta(days=days))
    return AgentNote.objects.get(pk=row.pk)


def osint(send):
    return [c.args[0] for c in send.call_args_list].count('news.tasks.pracownia_osint_task')


def status(row):
    return AgentNote.objects.get(pk=row.pk).status


def test_stale_notes_archived_once_and_never_deleted():
    old = [note('technolog', 'finding', days=9) for _ in range(11)]
    fresh = note('technolog', 'finding', days=1)
    total = AgentNote.objects.count()
    assert fuses.check_unused_outputs(Ctx(NOW)) == [] or all(a['key'] != 'petle:unused:technolog' for a in fuses.check_unused_outputs(Ctx(NOW)))
    assert all(status(n) == 'done' for n in old) and status(fresh) == 'new'
    assert AgentNote.objects.get(pk=old[0].pk).scores['auto']['reason'] == 'archiwum automatyczne'
    assert AgentNote.objects.count() == total
    logged = RepairAction.objects.filter(rule='petle:archiwum').count()
    assert logged == 11
    fix.remedy('check_unused_outputs', NOW)  # idempotentne
    assert RepairAction.objects.filter(rule='petle:archiwum').count() == 11


def test_ideas_low_rejected_high_to_sprint_forbidden_rejected():
    low = note('strateg', 'idea', days=8, score=30)
    high = note('strateg', 'idea', days=8, score=90, title='Alert mailowy dla dziennikarzy o nowych głosowaniach',
                scores={'effort': 'S', 'value': 8})
    banned = note('strateg', 'idea', days=8, score=95, title='Profil prywatnej osoby', scores={'verdict': 'niedozwolone'})
    fix.settle_all(NOW)
    assert status(low) == 'rejected' and 'poniżej 50' in AgentNote.objects.get(pk=low.pk).scores['auto']['reason']
    assert status(high) == 'accepted'
    ticket = BuildTicket.objects.get(note=high)
    assert ticket.status == 'proposed'
    assert status(banned) == 'rejected' and AgentNote.objects.get(pk=banned.pk).scores['auto']['reason'] == 'Prawnik: niedozwolone'
    assert not BuildTicket.objects.filter(note=banned).exists()
    fix.settle_all(NOW)
    assert BuildTicket.objects.filter(note=high).count() == 1


def test_middle_idea_gets_one_more_seba_review_then_threshold(monkeypatch):
    monkeypatch.setenv('SEBA_ENABLED', 'true')
    idea = note('strateg', 'idea', days=8, score=65)
    review = SebaReview.objects.get(note=idea)
    SebaReview.objects.filter(pk=review.pk).update(status='passed', rounds=1, created_at=NOW - timedelta(days=8))
    data = {}
    assert (idea.pk, 'requeued') in fix.settle_all(NOW, data=data)
    review.refresh_from_db()
    assert review.status == 'queued' and review.phase == 'critique' and str(review.pk) in data['seba']
    fix.save(data, NOW)
    assert 'petle:seba-queue' not in {f['key'] for f in fuses.quality(NOW)}  # ponowiona: 48 h bez alarmu
    assert 'petle:unused:strateg' not in {f['key'] for f in fuses.unused_outputs(NOW)}
    assert fix.settle_all(NOW) == [(idea.pk, 'waiting')]
    SebaReview.objects.filter(pk=review.pk).update(status='rejected', rounds=2)
    fix.settle_all(NOW)
    assert status(idea) == 'rejected' and 'druga ocena Seby' in AgentNote.objects.get(pk=idea.pk).scores['auto']['reason']


def test_silence_retriggers_with_daily_limit_then_alarms(isolated):
    send = isolated
    note('kontroler', 'audit', days=3)  # rytm 24 h, cisza
    assert 'petle:silent:kontroler' not in {a['key'] for a in fuses.check_silent_loops(Ctx(NOW))}  # pierwsza próba wstrzymuje alarm
    assert osint(send) == 1
    assert fix.suppressed('petle:silent:kontroler', NOW) == 'ponowiono 12:00'
    assert fix.suppressed('petle:silent:prawnik', NOW) == 'ponowiono 12:00'  # wspólne zadanie Pracowni: jedno zlecenie
    fuses.check_silent_loops(Ctx(NOW + timedelta(minutes=15)))
    assert osint(send) == 1  # naprawa w toku, bez kolejnego zlecenia
    report = raport_petli.build(NOW + timedelta(minutes=15))
    loop = next(l for c in report['categories'] for l in c['loops'] if l['key'] == 'kontroler')
    assert loop['state'] == 'warn' and loop['reason'].startswith('naprawa w toku: ponowiono 12:00')
    later = NOW + timedelta(hours=13)  # 01:00, ta sama doba limitów (reset o 02:00)
    with patch('django.utils.timezone.now', return_value=later):
        found = {a['key']: a for a in fuses.check_silent_loops(Ctx(later))}
    assert osint(send) == 2 and found['petle:silent:kontroler']['details']['naprawa'] == 'retried-again'
    data = fix.load()
    data['last_beat'] = {}
    fix.save(data, later)
    with patch('django.utils.timezone.now', return_value=later):
        found = {a['key']: a for a in fuses.check_silent_loops(Ctx(later))}
    assert osint(send) == 2 and found['petle:silent:kontroler']['details']['naprawa'] == 'exhausted'  # 2 na dobę
    assert RepairAction.objects.filter(rule='petle:ponowienie', result='retried', target__startswith='kartograf|').count() == 2


def test_no_free_model_defers_to_reset_without_alarm(isolated):
    send = isolated
    note('kontroler', 'audit', days=3)
    with patch('news.dyrygent.allowed', return_value=False):
        assert 'petle:silent:kontroler' not in {a['key'] for a in fuses.check_silent_loops(Ctx(NOW))}
        fuses.check_silent_loops(Ctx(NOW + timedelta(minutes=15)))
    assert osint(send) == 0 and 'news.tasks.duty_task' not in [c.args[0] for c in send.call_args_list]
    assert fix.suppressed('petle:silent:kontroler', NOW) == 'ponowienie po 02:00'
    assert RepairAction.objects.filter(rule='petle:ponowienie', result='skipped', target__startswith='kontroler|').count() == 1
    assert fix.next_reset(NOW).hour == 2


def test_broker_failure_raises_alarm(isolated):
    isolated.side_effect = ConnectionError('broker')
    note('kontroler', 'audit', days=3)
    found = fuses.check_silent_loops(Ctx(NOW))
    assert next(a for a in found if a['key'] == 'petle:silent:kontroler')['details']['naprawa'] == 'failed'
    assert RepairAction.objects.filter(rule='petle:ponowienie', result='failed').exists()


def test_transient_task_error_is_retried(isolated):
    note('kontroler', 'audit', days=0)
    RepairerState.objects.create(key='pulse:pracownia-osint', data={'result': 'error', 'summary': 'DataError',
                                                                     'repair_error': 'unknown', 'started_at': NOW.isoformat()})
    out = fix.retry_errors(NOW, {})
    assert list(out.values()).count('retried') == 1 and isolated.call_count == 1  # wspólne zadanie Pracowni: jedno zlecenie
    assert out['petle:error:kontroler'] in ('retried', 'pending')
    RepairerState.objects.filter(key='pulse:pracownia-osint').update(data={'result': 'error', 'summary': 'brak klucza API',
                                                                             'repair_error': 'permanent'})
    assert fix.retry_errors(NOW, {}) == {}


def test_duplicates_keep_newest(monkeypatch):
    rows = [note('strateg', days=3 - n, title=f'Newsletter tygodniowy z najlepszymi diagnozami {n}') for n in range(3)]
    fuses.check_quality(Ctx(NOW))
    newest = rows[-1]
    assert status(newest) == 'new'
    for row in rows[:-1]:
        assert status(row) == 'rejected'
        assert AgentNote.objects.get(pk=row.pk).scores['auto']['reason'] == f'duplikat #{newest.pk}'
    assert 'petle:duplicates:strateg' not in {f['key'] for f in fuses.quality(NOW)}
    assert AgentNote.objects.count() == 3


def test_seba_queue_requeue_local_then_threshold(monkeypatch):
    monkeypatch.setenv('SEBA_ENABLED', 'true')
    good = note('architekt', title='Dobry pomysł', score=85, scores={'author': {'company': 'google'}})
    weak = note('architekt', title='Słaby pomysł na coś zupełnie innego', score=40)
    SebaReview.objects.update(created_at=NOW - timedelta(hours=50), last_error='Brak darmowego modelu innej firmy.')
    assert fuses.check_quality(Ctx(NOW)) == []
    assert AgentNote.objects.get(pk=good.pk).scores['author']['company'] == 'local'
    assert AgentNote.objects.get(pk=good.pk).scores['author_before_auto'] == {'company': 'google'}
    later = NOW + timedelta(hours=49)
    with patch('django.utils.timezone.now', return_value=later):
        fuses.check_quality(Ctx(later))
    assert SebaReview.objects.get(note=good).status == 'passed' and SebaReview.objects.get(note=weak).status == 'rejected'
    assert AgentNote.objects.count() == 2


def test_tickets_auto_approved_after_48h_but_not_large_or_conditional(django_user_model):
    base = note('strateg', score=90)
    small = BuildTicket.objects.create(title='Mały', effort='S', created_at=NOW - timedelta(hours=50))
    large = BuildTicket.objects.create(title='Duży', effort='L', created_at=NOW - timedelta(hours=50))
    young = BuildTicket.objects.create(title='Świeży', effort='M', created_at=NOW - timedelta(hours=10))
    AgentNote.objects.filter(pk=base.pk).update(scores={'verdict': 'warunkowo'})
    cond = BuildTicket.objects.create(note=base, title='Warunkowy', effort='M', created_at=NOW - timedelta(hours=50))
    fuses.check_deadlines(Ctx(NOW))
    small.refresh_from_db()
    assert small.status == 'approved' and small.decided_by is None and sprint.row(small)['decided_note'] == sprint.AUTO_DECISION
    for t in (large, young, cond):
        t.refresh_from_db()
        assert t.status == 'proposed'
    fuses.check_deadlines(Ctx(NOW))
    assert RepairAction.objects.filter(rule='petle:bilet').count() == 1
    body = raport_petli.text(raport_petli.build(NOW))
    assert '== Do zbudowania przez Claude ==' in body and 'Zlecenie #' in body and 'Cel: Mały' in body
    assert f'Bilet #{large.pk} (L) czeka na decyzję' in body
    owner = django_user_model.objects.create_user(username='w', is_staff=True)
    sprint.decide(small, 'dropped', owner)  # właściciel może odłożyć w każdej chwili
    assert BuildTicket.objects.get(pk=small.pk).status == 'dropped'


def test_raportysta_reports_never_published_only_daily_line():
    from news.report_models import InstitutionalReport
    kind = InstitutionalReport._meta.get_field('kind').choices[0][0]
    report = InstitutionalReport.objects.create(kind=kind, audience='media', sample_key='k1', status='awaiting_approval',
                                                awaiting_since=NOW - timedelta(hours=30))
    for check in fuses.CHECKS:
        assert all(a['key'] != 'petle:reports-awaiting' for a in check(Ctx(NOW)))
    report.refresh_from_db()
    assert report.status == 'awaiting_approval' and report.approved_at is None
    body = raport_petli.text(raport_petli.build(NOW))
    assert body.count(f'#{report.pk} (nie publikujemy ich sami)') == 1


def test_report_and_gear_show_repairs(django_user_model):
    from rest_framework.test import APIClient
    for title in ('Mapa przetargów gmin', 'Oś czasu głosowań klubu', 'Rejestr umów ministerstw'):
        note('wynalazca', 'finding', days=9, title=title)
    note('wynalazca', 'finding', days=0, title='Nowe źródło danych KRS')
    fuses.check_unused_outputs(Ctx(NOW))
    report = raport_petli.build(NOW)
    loop = next(l for c in report['categories'] for l in c['loops'] if l['key'] == 'wynalazca')
    assert loop['state'] == 'ok' and loop['reason'] == 'naprawione 12:00' and len(loop['repairs']) == 3
    body = raport_petli.text(report)
    assert '== Naprawione automatycznie ==' in body and 'Archiwum automatyczne: #' in body and '—' not in body
    client = APIClient()
    client.force_authenticate(django_user_model.objects.create_user(username='s', is_staff=True))
    row = next(l for c in client.get('/api/staff/petle/').data['categories'] for l in c['loops'] if l['key'] == 'wynalazca')
    assert row['reason'] == 'naprawione 12:00' and row['repairs']


def test_switch_off_keeps_old_behaviour(monkeypatch):
    monkeypatch.setenv('LOOP_AUTOREPAIR', 'false')
    rows = [note('technolog', 'finding', days=9) for _ in range(11)]
    assert 'petle:unused:technolog' in {a['key'] for a in fuses.check_unused_outputs(Ctx(NOW))}
    assert all(status(r) == 'new' for r in rows) and not RepairAction.objects.exists()
