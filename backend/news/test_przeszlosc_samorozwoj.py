"""Samorozwój przeszłość.today (16.11.2026): samonaprawa kolejek, raport doby, kolejka rozwoju z bramkami."""
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from news import przeszlosc_samorozwoj as s
from news.public_records_models import PublicCollectionJob, PublicCollectionState
from news.test_drzewo_pieniedzy import rec

pytestmark = pytest.mark.django_db


def _state(source, **fields):
    return PublicCollectionState.objects.update_or_create(source=source, defaults={'lease_until': None, **fields})[0]


def _job(state, identity, failures, done=False, error='HTTPError'):
    return PublicCollectionJob.objects.create(state=state, identity=identity, url='https://api.sejm.gov.pl/x/' + identity,
                                              kind='list', failures=failures, done=done, last_error=error,
                                              retry_at=timezone.now() + timedelta(hours=24))


def test_odblokuj_parks_only_persistent_failures():
    state = _state('interpellations', status='deferred')
    stuck = _job(state, 'a', 12)
    young = _job(state, 'b', 3)
    parked = s.odblokuj(prog=10)
    stuck.refresh_from_db(); young.refresh_from_db()
    assert stuck.done and stuck.last_error == 'odlozone:HTTPError' and stuck.retry_at is None
    assert not young.done and young.failures == 3
    assert parked == {'interpellations': [('list', 'HTTPError')]}
    assert s.odblokuj(prog=10) == {}  # drugi bieg nic nie robi


def test_odblokuj_respects_access_gate_and_running_lease():
    walled = _state('assets', status='blocked_access_review')
    running = _state('questions', status='running',
                                                   lease_until=timezone.now() + timedelta(minutes=10))
    a, b = _job(walled, 'a', 20), _job(running, 'b', 20)
    assert s.odblokuj(prog=10) == {}
    a.refresh_from_db(); b.refresh_from_db()
    assert not a.done and not b.done


def test_parked_cycle_reseeds_after_refresh(monkeypatch):
    """Po odłożeniu cykl może się domknąć: brak oczekujących zadań, więc kolejny bieg zbieracza zakłada nowe."""
    state = _state('krs_changes', status='deferred')
    _job(state, 'a', 33)
    s.odblokuj(prog=10)
    assert not state.jobs.filter(done=False).exists()


def test_queue_states_and_gates(monkeypatch):
    from news.agent_models import BuildTicket
    from news.models import Source, SourceAccessInstruction
    monkeypatch.setenv('BIALA_LISTA_VAT_ENABLED', 'true')
    monkeypatch.delenv('BZP_API_ENABLED', raising=False)
    rec('biala_lista', 'status', '5260250995', {})
    q = s.kolejka()
    rows = {r['key']: r for r in q['pozycje']}
    assert rows['biala_lista']['stan'] == 'dziala'
    assert rows['bzp']['stan'] == 'czeka_na_zewnatrz' and rows['bzp']['na_kogo']  # kod jest, ale bez karty i z uwagą Prawnika
    assert rows['sudop']['stan'] == 'czeka_na_prawnika' and not rows['sudop']['kod']
    assert q['nastepna']['key'] == 'bzp'
    # Bez zatwierdzonej karty nie powstaje żaden bilet.
    assert s.zglos_budowe(rows['sudop']) is None
    # Prawnik zatwierdza kartę SUDOP: pozycja przechodzi do budowy i dostaje dokładnie jeden bilet (proposed, nic nie włączone).
    source = Source.objects.create(name='SUDOP', url='https://sudop.uokik.gov.pl/')
    SourceAccessInstruction.objects.create(
        source=source, status='approved', channel='api', endpoint='https://sudop.uokik.gov.pl/api/', terms_url='https://uokik.gov.pl/',
        evidence={'url': 'https://uokik.gov.pl/'}, minimum_interval_seconds=5, daily_request_cap=100,
        reviewed_at=timezone.now(), reviewed_by='prawnik')
    sudop = s.stan_pozycji(next(p for p in s.KOLEJKA if p.key == 'sudop'))
    assert sudop['stan'] == 'do_budowy' and sudop['karta']
    first = s.zglos_budowe(sudop)
    assert first and s.zglos_budowe(sudop) is None
    ticket = BuildTicket.objects.get(pk=first)
    assert ticket.status == 'proposed' and 'access_gate' in ticket.brief and 'SUDOP_ENABLED' in ticket.brief


def test_sensitive_item_never_gets_ticket(monkeypatch):
    from news.models import Source, SourceAccessInstruction
    source = Source.objects.create(name='CRBR', url='https://crbr.podatki.gov.pl/')
    SourceAccessInstruction.objects.create(
        source=source, status='approved', channel='api', endpoint='https://crbr.podatki.gov.pl/api/', terms_url='https://x.gov.pl/',
        evidence={'a': 1}, minimum_interval_seconds=5, daily_request_cap=10, reviewed_at=timezone.now(), reviewed_by='prawnik')
    crbr = s.stan_pozycji(next(p for p in s.KOLEJKA if p.key == 'crbr'))
    assert crbr['stan'] == 'decyzja_wlasciciela' and crbr['na_kogo'] == 'właściciel'
    assert s.zglos_budowe(crbr) is None


def test_shared_host_card_of_other_source_does_not_count():
    """Produkcja 17.11: karty ministerstw na www.gov.pl dawały „do_budowy” spółkom SP i sankcjom."""
    from news.models import Source, SourceAccessInstruction
    source = Source.objects.create(name='MAP', url='https://www.gov.pl/web/aktywa-panstwowe')
    card = SourceAccessInstruction.objects.create(
        source=source, status='approved', channel='html', endpoint='https://www.gov.pl/web/aktywa-panstwowe/', terms_url='https://www.gov.pl/',
        evidence={'url': 'https://www.gov.pl/'}, minimum_interval_seconds=5, daily_request_cap=10, reviewed_at=timezone.now(), reviewed_by='prawnik')
    ssp = next(p for p in s.KOLEJKA if p.key == 'ssp')
    assert s.stan_pozycji(ssp)['stan'] == 'czeka_na_prawnika'
    card.evidence = {'url': 'https://www.gov.pl/', 'kolejka': 'ssp'}
    card.save()
    assert s.stan_pozycji(ssp)['stan'] == 'do_budowy'
    assert s.stan_pozycji(next(p for p in s.KOLEJKA if p.key == 'sankcje'))['stan'] == 'czeka_na_prawnika'


def test_queue_remembers_since_date():
    now = timezone.now()
    s.kolejka(now - timedelta(days=5), zapisz=True)
    q = s.kolejka(now)
    assert q['nastepna']['od'].startswith((now - timedelta(days=5)).date().isoformat())


def test_doba_counts_new_records_and_failures(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_TED_ENABLED', 'true')
    rec('ted', 'notice', '1-2026', {})
    first = s.doba(zapisz=True)
    assert first['pierwszy_raport'] and any('pierwsza migawka' in line for line in s.lines(first))
    rec('ted', 'notice', '2-2026', {})
    rec('ted', 'notice', '3-2026', {})
    state = _state('fts', status='deferred')
    _job(state, 'y', 4, error='fts_header_missing')
    data = s.doba(parked={'questions': [('list', 'HTTPError')]})
    assert data['nowe']['zrodlo:ted'] == 2
    text = '\n'.join(s.lines(data))
    assert 'ted +2' in text and 'fts: 1 zadań z błędem, najczęściej fts_header_missing' in text
    assert 'Odłożone automatycznie' in text and 'questions 1' in text
    assert 'Następna pozycja z listy rozwoju' in text
    assert chr(0x2014) not in text and chr(0x2013) not in text  # zero długich myślników


def test_run_saves_report_used_by_loop_mail(monkeypatch):
    from news import raport_petli
    from news.models import RepairerState
    result = s.run()
    assert result['status'] == 'ok' and result['produced'] == 1
    assert RepairerState.objects.filter(key__startswith=s.DOBA_KEY).exclude(key=s.SNAPSHOT_KEY).exists()
    assert s.report_lines()[0] != '(zadanie przeszlosc-doba jeszcze dziś nie ruszyło; odczyt na żywo)'
    report = raport_petli.build()
    assert report['przeszlosc'] and '== przeszłość.today: dane doby ==' in raport_petli.text(report)
    monkeypatch.setenv('PRZESZLOSC_SAMOROZWOJ_ENABLED', 'false')
    assert s.run() == {'status': 'disabled'}


def test_beat_registry_and_command(capsys):
    from config.celery import app
    from news import agent_registry
    from news.daily_schedule import BEAT_PLAN
    assert BEAT_PLAN['przeszlosc-doba'] == ('przeszlosc_doba_task', {'hour': 6, 'minute': 35})
    assert app.conf.beat_schedule['przeszlosc-doba']['task'] == 'news.tasks.przeszlosc_doba_task'
    assert agent_registry.REGISTRY['przeszlosc-doba']['flag'] == 'PRZESZLOSC_SAMOROZWOJ_ENABLED'
    call_command('przeszlosc_doba', '--kolejka')
    out = capsys.readouterr().out
    assert 'sudop' in out and 'bzp' in out


def test_weekly_niw_success_without_changes_is_not_stale(monkeypatch):
    """NIW i OPP stały jako „zaległe” od 13.10, bo plik bez zmian nie odświeża fetched_at; udany bieg zapisuje datę sukcesu."""
    from news import przeszlosc_stan, tasks
    monkeypatch.setattr(tasks, 'call_command', lambda *a, **k: None, raising=False)
    monkeypatch.setattr('django.core.management.call_command', lambda *a, **k: None)
    rec('niw', 'grant_pl', 'U-1', {})
    from news.public_records_models import PublicRecord
    PublicRecord.objects.filter(source='niw').update(fetched_at=timezone.now() - timedelta(days=35))
    assert {r['key']: r for r in przeszlosc_stan.sources()}['niw']['status'] == 'stale'
    assert tasks.przeszlosc_niw_task() == {'status': 'ok'}
    assert {r['key']: r for r in przeszlosc_stan.sources()}['niw']['status'] == 'ok'
