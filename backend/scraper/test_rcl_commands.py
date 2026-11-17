"""Polecenia zarządzania i zadanie Celery zbieracza RCL.  Bez sieci."""
import json
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from freezegun import freeze_time
import pytest

from news.models import LegislativeProject, Source, SourceAccessInstruction
from scraper import rcl_harvest
from scraper.rcl_testsupport import no_network  # noqa: F401
from scraper.management.commands.configure_rcl_source import LETTER, configure

pytestmark = pytest.mark.django_db


def run(*args, **kwargs):
    out = StringIO()
    call_command(*args, stdout=out, **kwargs)
    return out.getvalue()


def test_configure_plan_changes_nothing_and_apply_creates_a_valid_card():
    assert 'Bez --apply nie zmieniam bazy' in run('configure_rcl_source')
    assert not Source.objects.exists()
    run('configure_rcl_source', '--apply')
    source, instruction = rcl_harvest.configured_access()
    assert source.url == 'https://legislacja.rcl.gov.pl/' and instruction is not None
    assert instruction.minimum_interval_seconds == 5 and instruction.evidence['letter_signature'] == LETTER
    assert instruction.evidence['letter_date'] == '2026-10-21'
    assert any('User-Agent: iapply-legislacja/1.0' in item for item in instruction.evidence['conditions'])
    run('configure_rcl_source', '--apply')   # idempotentne: ta sama karta, bez nowej wersji
    assert SourceAccessInstruction.objects.filter(source=source).count() == 1


def test_card_covers_robots_pages_and_documents_but_nothing_on_other_hosts():
    from scraper.access_gate import approved_instruction
    source, _ = configure('test')
    html = SourceAccessInstruction.Channel.HTML
    for url in ('https://legislacja.rcl.gov.pl/robots.txt', 'https://legislacja.rcl.gov.pl/lista?typeId=2',
                'https://legislacja.rcl.gov.pl/projekt/1/katalog/2', 'https://legislacja.rcl.gov.pl/docs//2/1/2/dokument3.pdf'):
        assert approved_instruction(source, html, url) is not None
    for url in ('https://rcl.gov.pl/', 'https://www.gov.pl/web/premier', 'http://legislacja.rcl.gov.pl/lista'):
        assert approved_instruction(source, html, url) is None


def test_without_a_card_the_collector_has_no_access():
    assert rcl_harvest.configured_access() == (None, None)
    configure('test')
    SourceAccessInstruction.objects.update(minimum_interval_seconds=5, status='suspended')
    assert rcl_harvest.configured_access()[1] is None


def test_status_needs_no_network_and_reports_conditions(monkeypatch, no_network):  # noqa: F811
    monkeypatch.delenv('RCL_FETCH_ENABLED', raising=False)
    with freeze_time('2026-10-22 11:00:00'):   # 13:00 w Polsce
        status = json.loads(run('rcl_zbieracz', '--status'))
    assert status['RCL_FETCH_ENABLED'] is False and status['window_open_now'] is False
    assert status['source_configured'] is False and status['nightly_budget'] == 3000 and status['files_enabled'] is False
    assert not no_network


def test_dry_run_command_prints_summary_and_stores_nothing(no_network):  # noqa: F811
    summary = json.loads(run('rcl_zbieracz', '--dry-run'))
    assert summary['status'] == 'dry_run' and summary['would_store']['documents'] > 0
    assert LegislativeProject.objects.count() == 0 and not no_network


def test_manual_run_outside_window_or_without_flag_sends_nothing(monkeypatch, no_network):  # noqa: F811
    monkeypatch.delenv('RCL_FETCH_ENABLED', raising=False)
    assert json.loads(run('rcl_zbieracz'))['status'] == 'disabled'
    monkeypatch.setenv('RCL_FETCH_ENABLED', 'true')
    with freeze_time('2026-10-22 10:00:00'):    # 12:00 w Polsce
        assert json.loads(run('rcl_zbieracz'))['status'] == 'outside_window'
    assert not no_network


def test_command_argument_validation():
    with pytest.raises(CommandError):
        call_command('rcl_zbieracz', '--limit-zapytan', '99999')
    with pytest.raises(CommandError):
        call_command('rcl_zbieracz', '--zrzut', 'x')


def test_celery_task_is_registered_and_idle_without_the_flag(monkeypatch, no_network):  # noqa: F811
    from scraper.tasks import rcl_night_task
    monkeypatch.delenv('RCL_FETCH_ENABLED', raising=False)
    assert rcl_night_task.name == 'scraper.tasks.rcl_night_task'
    assert rcl_night_task()['status'] == 'disabled'
    assert not no_network


def test_recon_only_runs_once_per_night(monkeypatch, no_network):  # noqa: F811
    from django.core.cache import cache
    from scraper import tasks
    cache.clear()
    monkeypatch.setenv('RCL_RECON_ONLY', 'true')
    calls = []
    monkeypatch.setattr(rcl_harvest, 'run_night', lambda **kw: calls.append(kw) or {'status': 'ran'})
    assert tasks.rcl_night_task()['status'] == 'ran'
    assert calls[0]['recon'] is True and calls[0]['dump_dir'] == '/var/tmp/rcl-recon'
    assert tasks.rcl_night_task()['status'] == 'recon_done' and len(calls) == 1
    monkeypatch.delenv('RCL_RECON_ONLY')
    tasks.rcl_night_task()
    assert calls[-1] == {'seconds': 480}
    cache.clear()
