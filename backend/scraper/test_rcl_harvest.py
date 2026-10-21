"""Zbieracz RCL: kolejność nocy, wersjonowanie, atrybucja źródła, kursory, przerwania.  Bez sieci; strony z fixtures."""
from datetime import date, datetime, timedelta, timezone as dt_timezone
import hashlib
import re

from django.utils import timezone
from freezegun import freeze_time
import pytest

from news.models import (ImportState, LegislativeChange, LegislativeDocument, LegislativeProject, LegislativeStage,
                         RclFetchEvent)
from scraper import rcl_harvest as harvest
from scraper import rcl_parser
from scraper.management.commands.configure_rcl_source import configure
from scraper.rcl_client import RclResponse, RclStop, RclTransient
from scraper.rcl_testsupport import Clock, at, fixture_text, http_error, no_network, ok_response  # noqa: F401

PROJECT = 12414100
STAGE = 13223895
PAGE = fixture_text('katalog_13223895_konsultacje.html')       # strona projektu 12414100 (z rozwiniętym etapem)
CATALOG = fixture_text('katalog_13223895_konsultacje_z_uwagami.html')
LIST_HTML = fixture_text('lista_typ2.html')


def utc(moment):
    return moment.astimezone(dt_timezone.utc)


def list_html(rows):
    """Strona listy RCL z podanymi wierszami (rcl_id, tytuł, modyfikacja, utworzenie)."""
    head, rest = LIST_HTML.split('<tbody>', 1)
    tail = rest.split('</tbody>', 1)[1]
    body = ''.join(
        f'<tr class=""><td><a href="/projekt/{i}">{title}</a></td><td><a href="/lista?applicantId=1">Minister Zdrowia</a></td>'
        f'<td><a href="https://www.gov.pl/web/premier/wplip-rm">UD{i % 1000}</a></td>'
        f'<td class="text-center">{created:%d-%m-%Y}</td><td class="text-center">{modified:%d-%m-%Y}</td></tr>'
        for i, title, modified, created in rows)
    return head + '<tbody>' + body + '</tbody>' + tail


class Scripted:
    """Klient podstawiony: odpowiada z fixtures i zapisuje kolejność zapytań."""

    def __init__(self, lists=None, catalog=CATALOG, page=PAGE):
        self.requests_made = 0
        self.robots_override_used = False
        self.log = []
        self.lists = lists or {}          # (sKey, pNumber) -> html
        self.catalog, self.page = catalog, page
        self.fail = {}

    def get(self, path_or_url, *, kind='page'):
        path = path_or_url.replace('https://legislacja.rcl.gov.pl', '')
        self.log.append(path)
        self.requests_made += 1
        now = timezone.now()
        if path in self.fail:
            raise self.fail[path]
        if path.startswith('/lista'):
            key = re.search(r'sKey=(\w+)', path)[1], int(re.search(r'pNumber=(\d+)', path)[1])
            return RclResponse(path, 200, self.lists.get(key, list_html([])).encode(), now)
        if '/katalog/' in path:
            html = self.catalog if path.endswith(f'/{STAGE}') else self.page
            return RclResponse(path, 200, html.encode(), now)
        return RclResponse(path, 200, self.page.encode(), now)


def row(i, modified=date(2026, 10, 20), created=date(2026, 9, 1), title=None):
    return (i, title or f'Projekt ustawy numer {i}', modified, created)


@pytest.fixture
def project(db):
    p = LegislativeProject.objects.create(rcl_id=PROJECT, act_type_id=2, title='Stary tytuł', source_url='x', needs_refresh=True)
    return p


# --- lista i dziennik zmian ---

def test_list_row_create_change_and_no_silent_overwrite(db):
    fetched = timezone.now()
    base = {'rcl_id': 5, 'title': 'T1', 'applicant': 'Minister A', 'applicant_id': '1', 'wykaz_number': 'UD5',
            'wykaz_url': '', 'created_on': date(2026, 1, 2), 'modified_on': date(2026, 2, 3)}
    assert harvest.upsert_list_row(base, 2, 'Projekty ustaw', fetched, 1) == 'created'
    project = LegislativeProject.objects.get(rcl_id=5)
    assert project.needs_refresh and project.refresh_priority == 1
    assert project.source_url == 'https://legislacja.rcl.gov.pl/projekt/5' and project.list_fetched_at == fetched
    assert harvest.upsert_list_row(base, 2, 'Projekty ustaw', fetched, 1) == 'same'
    assert LegislativeChange.objects.count() == 1
    LegislativeProject.objects.filter(pk=project.pk).update(needs_refresh=False, refresh_priority=0, fetched_at=fetched)
    changed = {**base, 'title': 'T2', 'modified_on': date(2026, 3, 4)}
    assert harvest.upsert_list_row(changed, 2, 'Projekty ustaw', fetched, 1) == 'changed'
    change = LegislativeChange.objects.filter(kind='changed').get()
    assert change.changes == {'title': ['T1', 'T2'], 'list_modified_on': ['2026-02-03', '2026-03-04']}
    project.refresh_from_db()
    assert project.title == 'T2' and project.needs_refresh and project.refresh_priority == 1
    with pytest.raises(ValueError):
        change.save()  # dziennik jest tylko do dopisywania


def test_changelog_survives_when_a_value_returns(db):
    fetched = timezone.now()
    base = {'rcl_id': 6, 'title': 'A', 'applicant': '', 'applicant_id': '', 'wykaz_number': '', 'wykaz_url': '',
            'created_on': None, 'modified_on': date(2026, 1, 1)}
    harvest.upsert_list_row(base, 2, '', fetched, 0)
    harvest.upsert_list_row({**base, 'title': 'B'}, 2, '', fetched, 0)
    harvest.upsert_list_row(base, 2, '', fetched, 0)
    assert [c.changes['title'] for c in LegislativeChange.objects.filter(kind='changed').order_by('id')] == [['A', 'B'], ['B', 'A']]


# --- projekt, etapy, dokumenty ---

def test_refresh_stores_project_stages_documents_with_source_and_fetch_date(project):
    client = Scripted()
    run = harvest.Run()
    harvest.refresh_project(client, run, project)
    project.refresh_from_db()
    assert project.title.startswith('Projekt ustawy o udziale Rzeczypospolitej') or project.title != 'Stary tytuł'
    assert project.source_url == 'https://legislacja.rcl.gov.pl/projekt/12414100' and project.fetched_at is not None
    assert not project.needs_refresh and project.content_hash
    assert project.stages.count() == 14
    assert project.stages.get(rcl_id=STAGE).catalog_fetched_at is not None
    docs = LegislativeDocument.objects.filter(project=project)
    assert docs.count() == 9
    assert set(docs.values_list('category', flat=True)) == {'project', 'osr', 'justification', 'other', 'cover_letter', 'position', 'comment_table'}
    position = docs.get(rcl_doc_id=795001)
    assert position.author == 'Stowarzyszenie Przykładowe' and position.created_on == date(2026, 9, 10)
    assert position.source_page_url.endswith(f'/projekt/{PROJECT}/katalog/{STAGE}') and position.fetched_at is not None
    assert not any('pracownik' in (d.name + d.author).lower() for d in docs)
    # strona projektu + 1 katalog na każdy etap z odnośnikiem (3 etapy w tej kopii mają katalog)
    assert client.requests_made == 1 + project.stages.exclude(catalog_url='').count()


def test_unchanged_second_refresh_adds_no_changes(project):
    harvest.refresh_project(Scripted(), harvest.Run(), project)
    before = LegislativeChange.objects.count()
    project.refresh_from_db()
    # etapy nie zmieniły daty modyfikacji, więc ani strona nie przynosi zmian, ani katalogi nie są pobierane
    client = Scripted()
    harvest.refresh_project(client, harvest.Run(), project)
    assert LegislativeChange.objects.count() == before and client.requests_made == 1


def test_changes_removals_and_reappearance_are_logged_not_overwritten(project):
    harvest.refresh_project(Scripted(), harvest.Run(), project)
    stage = LegislativeStage.objects.get(project=project, rcl_id=STAGE)
    when = timezone.now() + timedelta(hours=1)
    url = 'https://legislacja.rcl.gov.pl/projekt/12414100/katalog/13223895'

    renamed = CATALOG.replace('Stanowisko Izby Wzorcowej.docx', 'Stanowisko Izby Wzorcowej - poprawione.docx')
    removed = renamed.replace('Uwagi do projektu ustawy - Stowarzyszenie Przykładowe.pdf', 'Uwagi do projektu ustawy - Stowarzyszenie Przykładowe.pdf')
    dropped = re.sub(r'<ul>\s*<li class="doc" onclick="">\s*<a href="[^"]*dokument795001\.pdf">.*?</li>\s*</ul>', '', renamed, flags=re.S)
    assert 'dokument795001' not in dropped
    counts = harvest.apply_catalog(project, stage, rcl_parser.parse_stage_catalog(dropped, STAGE), when, url)
    assert counts['docs_changed'] == 1 and counts['docs_removed'] == 1
    doc = LegislativeDocument.objects.get(project=project, rcl_doc_id=795002)
    assert doc.name == 'Stanowisko Izby Wzorcowej - poprawione.docx'
    gone = LegislativeDocument.objects.get(project=project, rcl_doc_id=795001)
    assert gone.removed_at == when and gone.name.startswith('Uwagi do projektu')   # nic nie jest kasowane
    kinds = {(c.entity_key, c.kind): c.changes for c in LegislativeChange.objects.filter(entity='document')}
    assert kinds[('795002', 'changed')]['name'] == ['Stanowisko Izby Wzorcowej.docx', 'Stanowisko Izby Wzorcowej - poprawione.docx']
    assert ('795001', 'removed') in kinds
    # powrót dokumentu
    counts = harvest.apply_catalog(project, stage, rcl_parser.parse_stage_catalog(renamed, STAGE), when + timedelta(days=1), url)
    gone.refresh_from_db()
    assert gone.removed_at is None and counts['docs_changed'] == 1
    assert LegislativeChange.objects.filter(entity='document', entity_key='795001', kind='reappeared').exists()


def test_project_page_changes_are_versioned(project):
    harvest.refresh_project(Scripted(), harvest.Run(), project)
    first_hash = LegislativeProject.objects.get(pk=project.pk).content_hash
    new_page = PAGE.replace('>otwarty<', '>zamknięty<')
    assert new_page != PAGE
    LegislativeStage.objects.filter(project=project).update(catalog_fetched_at=timezone.now())
    harvest.refresh_project(Scripted(page=new_page), harvest.Run(), LegislativeProject.objects.get(pk=project.pk))
    project.refresh_from_db()
    assert project.status == 'zamknięty' and project.content_hash != first_hash
    change = LegislativeChange.objects.filter(entity='project', kind='changed').latest('id')
    assert change.changes['status'] == ['otwarty', 'zamknięty']


def test_catalog_fetch_rules(project):
    harvest.refresh_project(Scripted(), harvest.Run(), project)
    stage = LegislativeStage.objects.get(project=project, rcl_id=STAGE)
    assert not harvest._stage_needs_catalog(stage)
    stage.modified_on = date(2026, 9, 30)
    assert harvest._stage_needs_catalog(stage)
    stage.modified_on = stage.catalog_modified_seen
    stage.catalog_fetched_at = None
    assert harvest._stage_needs_catalog(stage)
    stage.catalog_url = ''
    assert not harvest._stage_needs_catalog(stage)


def test_parse_failure_keeps_existing_data_and_project_leaves_queue_after_three_nights(project):
    harvest.refresh_project(Scripted(), harvest.Run(), project)
    snapshot = LegislativeProject.objects.values().get(pk=project.pk)
    LegislativeProject.objects.filter(pk=project.pk).update(needs_refresh=True)
    for night in range(3):
        run = harvest.Run()
        harvest.refresh_project(Scripted(page='<html><body>inna strona</body></html>'), run, LegislativeProject.objects.get(pk=project.pk))
        assert run.counters['parse_errors'] == 1
    after = LegislativeProject.objects.values().get(pk=project.pk)
    assert after['title'] == snapshot['title'] and after['content_hash'] == snapshot['content_hash']
    assert after['refresh_failures'] == 3 and after['last_error'].startswith('parse:') and after['needs_refresh']
    assert RclFetchEvent.objects.filter(kind='parse_error').count() == 3
    client = Scripted()
    harvest.drain_queue(client, harvest.Run())
    assert client.requests_made == 0   # po trzech błędach projekt czeka na ręczne sprawdzenie


def test_a_type_with_unreadable_pages_is_skipped_after_three_failures_and_others_continue(db):
    for i in range(1, 6):
        LegislativeProject.objects.create(rcl_id=100 + i, act_type_id=6, title=f'OSR {i}', source_url='x', list_modified_on=date(2026, 10, 25))
    LegislativeProject.objects.create(rcl_id=PROJECT, act_type_id=2, title='Ustawa', source_url='x', list_modified_on=date(2026, 10, 1))
    client = Scripted()
    original = client.get

    def get(path, **kwargs):
        short = path.replace('https://legislacja.rcl.gov.pl', '')
        if re.fullmatch(r'/projekt/10[1-5]', short):          # strony tego rodzaju mają inny układ
            client.requests_made += 1
            client.log.append(short)
            return RclResponse(path, 200, b'<html>inny uklad</html>', timezone.now())
        return original(path, **kwargs)

    client.get = get
    run = harvest.Run()
    harvest.drain_queue(client, run)
    assert run.counters['parse_errors'] == 3 and run.skipped_types() == [6]
    assert [p for p in client.log if p.startswith('/projekt/10')] == ['/projekt/105', '/projekt/104', '/projekt/103']
    assert LegislativeProject.objects.get(rcl_id=PROJECT).fetched_at is not None      # typ 2 przeszedł mimo to
    assert LegislativeProject.objects.get(rcl_id=105).refresh_failures == 1


def test_five_transient_errors_in_a_row_stop_the_run(db):
    for i in range(1, 8):
        LegislativeProject.objects.create(rcl_id=200 + i, act_type_id=2, title=f'P{i}', source_url='x')
    client = Scripted()
    for i in range(1, 8):
        client.fail[f'/projekt/{200 + i}'] = RclTransient('http_500')
    with pytest.raises(RclStop) as stop:
        harvest.drain_queue(client, harvest.Run())
    assert stop.value.reason == 'too_many_errors' and client.requests_made == 5


def test_transient_error_does_not_mark_project_done(project):
    client = Scripted()
    client.fail[f'/projekt/{PROJECT}'] = RclTransient('http_500')
    run = harvest.Run()
    harvest.refresh_project(client, run, project)
    project.refresh_from_db()
    assert project.needs_refresh and project.refresh_failures == 1 and run.counters['transient_errors'] == 1


# --- kolejność nocy, kursory, znacznik ---

def test_news_first_then_archive_order(db):
    lists = {('modifiedDate', 1): list_html([row(201), row(202)]),
             ('createDate', 1): list_html([row(301, modified=date(2026, 1, 5)), row(302, modified=date(2026, 1, 6))])}
    client = Scripted(lists=lists)
    summary = harvest.run_with_client(client, types=(2,), archive_pages=1)
    kinds = ['news' if 'modifiedDate' in p else 'archive' if 'createDate' in p else 'project' for p in client.log if p.startswith(('/lista', '/projekt/20', '/projekt/30'))]
    assert kinds == ['news', 'project', 'project', 'archive', 'project', 'project']
    projects = [p for p in client.log if re.fullmatch(r'/projekt/\d+', p)]
    # w obrębie grupy: data modyfikacji malejąco, przy remisie wyższy numer
    assert projects == ['/projekt/202', '/projekt/201', '/projekt/302', '/projekt/301']
    assert summary['stopped'] == 'finished' and summary['counters']['projects_created'] == 4


def test_news_watermark_stops_at_old_rows_and_first_run_reads_one_page(db):
    day = date(2026, 10, 20)
    page1 = list_html([row(i, modified=day) for i in range(1, 101)])
    client = Scripted(lists={('modifiedDate', 1): page1, ('modifiedDate', 2): list_html([row(500)])})
    harvest.news_pass(client, harvest.Run(), 2)
    assert [p for p in client.log if p.startswith('/lista')] == [harvest.list_url(2, 1)]    # pierwszy raz: tylko strona 1
    assert ImportState.objects.get(name='rcl:news:2').cursor['watermark'] == '2026-10-20'
    # kolejna noc: wiersze nowe, potem starsze niż znacznik minus dzień - czytanie kończy się na tej stronie
    newer = [row(i, modified=date(2026, 10, 22)) for i in range(1000, 1003)]
    older = [row(i, modified=date(2026, 10, 10)) for i in range(2000, 2097)]
    client = Scripted(lists={('modifiedDate', 1): list_html(newer + older), ('modifiedDate', 2): list_html([row(9)])})
    run = harvest.Run()
    harvest.news_pass(client, run, 2)
    assert [p for p in client.log if p.startswith('/lista')] == [harvest.list_url(2, 1)]
    assert run.counters['projects_created'] == 3 and not LegislativeProject.objects.filter(rcl_id__gte=2000).exists()
    assert ImportState.objects.get(name='rcl:news:2').cursor['watermark'] == '2026-10-22'
    # cała strona nowsza niż znacznik - idziemy na następną
    client = Scripted(lists={('modifiedDate', 1): list_html([row(i, modified=date(2026, 10, 25)) for i in range(3000, 3100)]),
                             ('modifiedDate', 2): list_html([row(9, modified=date(2026, 10, 1))])})
    harvest.news_pass(client, harvest.Run(), 2)
    assert [p for p in client.log if p.startswith('/lista')] == [harvest.list_url(2, 1), harvest.list_url(2, 2)]


def test_archive_cursor_resumes_and_finishes(db):
    full = lambda start: list_html([row(i, created=date(2026, 1, 1)) for i in range(start, start + 100)])  # noqa: E731
    lists = {('createDate', 1): full(1), ('createDate', 2): full(101), ('createDate', 3): list_html([row(999)])}
    client = Scripted(lists=lists)
    harvest.archive_list_pass(client, harvest.Run(), 2, pages=2)
    cursor = ImportState.objects.get(name='rcl:archive:2').cursor
    assert cursor['page'] == 3 and not cursor['complete'] and LegislativeProject.objects.count() == 200
    client = Scripted(lists=lists)
    harvest.archive_list_pass(client, harvest.Run(), 2, pages=5)
    assert client.log == [harvest.list_url(2, 3, 'createDate', 'asc')]      # wznowione od zapisanej strony
    assert ImportState.objects.get(name='rcl:archive:2').cursor['complete'] is True
    client = Scripted(lists=lists)
    harvest.archive_list_pass(client, harvest.Run(), 2, pages=5)
    assert client.log == []      # skończone, ponowne przejście dopiero po 30 dniach


# --- przebieg nocny przez prawdziwego klienta, bez sieci ---

@pytest.fixture
def night(db, monkeypatch):
    """Źródło z kartą, flaga produkcyjna i transport RCL podstawiony odpowiedziami z fixtures."""
    monkeypatch.setenv('RCL_FETCH_ENABLED', 'true')
    monkeypatch.delenv('RCL_ROBOTS_OVERRIDE', raising=False)
    configure('test')

    class Site:
        calls = []
        script = {}
        clock = None
        lists = {('modifiedDate', 1): list_html([row(201), row(202)]), ('createDate', 1): list_html([row(301)])}

        def __call__(self, url, *, requested_kind, **kwargs):
            self.calls.append(url)
            if self.clock:
                self.mono_at = self.clock.monotonic()
            path = url.replace('https://legislacja.rcl.gov.pl', '')
            if url in self.script:
                outcome = self.script[url]
                if isinstance(outcome, BaseException):
                    raise outcome
                return outcome, None
            if path == '/robots.txt':
                return ok_response('User-agent: iapply-legislacja\nAllow: /\n'), None
            if path.startswith('/lista'):
                key = re.search(r'sKey=(\w+)', path)[1], int(re.search(r'pNumber=(\d+)', path)[1])
                return ok_response(self.lists.get(key, list_html([]))), None
            if '/katalog/' in path:
                return ok_response(CATALOG if path.endswith(f'/{STAGE}') else PAGE), None
            return ok_response(PAGE), None

    site = Site()
    site.calls = []
    site.script = {}
    monkeypatch.setattr('scraper.rcl_client.fetch_response_once', site)
    return site


def test_run_night_does_nothing_without_flag_or_outside_window_or_card(night, monkeypatch):
    with freeze_time(utc(at(3))) as freezer:
        clock = Clock(freezer)
        monkeypatch.delenv('RCL_FETCH_ENABLED')
        assert harvest.run_night(sleep=clock.sleep, monotonic=clock.monotonic)['status'] == 'disabled'
        monkeypatch.setenv('RCL_FETCH_ENABLED', 'true')
    with freeze_time(utc(at(0, 59, 50))) as freezer:
        clock = Clock(freezer)
        assert harvest.run_night(sleep=clock.sleep, monotonic=clock.monotonic)['status'] == 'outside_window'
    from news.models import SourceAccessInstruction
    SourceAccessInstruction.objects.update(status='suspended')
    with freeze_time(utc(at(3))) as freezer:
        clock = Clock(freezer)
        assert harvest.run_night(sleep=clock.sleep, monotonic=clock.monotonic)['status'] == 'no_access_card'
    assert night.calls == []


def test_run_night_full_pass_counts_budget_and_stays_resumable(night, monkeypatch):
    with freeze_time(utc(at(2))) as freezer:
        clock = Clock(freezer)
        night.clock = clock
        summary = harvest.run_night(budget=12, sleep=clock.sleep, monotonic=clock.monotonic)
    assert summary['status'] == 'ran' and summary['stopped'] == 'budget' and summary['requests'] == 12
    assert len(night.calls) == 12 and night.calls[0].endswith('/robots.txt')
    assert ImportState.objects.get(name='rcl:night').cursor == {'date': '2026-10-22', 'used': 12}
    # druga porcja tej samej nocy ma tylko resztę budżetu
    with freeze_time(utc(at(2, 30))) as freezer:
        clock = Clock(freezer)
        again = harvest.run_night(budget=14, sleep=clock.sleep, monotonic=clock.monotonic)
    assert again['requests'] == 2 and again['stopped'] == 'budget'
    with freeze_time(utc(at(2, 40))) as freezer:
        clock = Clock(freezer)
        assert harvest.run_night(budget=14, sleep=clock.sleep, monotonic=clock.monotonic)['status'] == 'budget_exhausted'
    assert LegislativeProject.objects.filter(rcl_id__in=[201, 202]).count() == 2
    # nowość przed archiwum także w porcjach: w pierwszych 12 zapytaniach nie ma jeszcze listy archiwum
    assert not any('createDate' in call for call in night.calls[:12])


def test_run_night_halts_on_429_and_next_slice_sends_nothing(night):
    with freeze_time(utc(at(2))) as freezer:
        clock = Clock(freezer)
        night.script['https://legislacja.rcl.gov.pl/projekt/202'] = http_error(429, {'Retry-After': '10'})
        summary = harvest.run_night(sleep=clock.sleep, monotonic=clock.monotonic)
        assert summary['stopped'] == 'halt_429'
        sent = len(night.calls)
        freezer.tick(timedelta(minutes=10))
        later = harvest.run_night(sleep=clock.sleep, monotonic=clock.monotonic)
        assert later['status'] == 'halted' and len(night.calls) == sent
    assert RclFetchEvent.objects.filter(kind='halt_429').count() == 1
    # projekt, na którym przerwano, nie jest uznany za pobrany
    assert LegislativeProject.objects.get(rcl_id=202).needs_refresh


def test_run_night_stops_itself_before_six(night):
    with freeze_time(utc(at(5, 58, 50))) as freezer:
        clock = Clock(freezer)
        night.clock = clock
        summary = harvest.run_night(sleep=clock.sleep, monotonic=clock.monotonic)
        end = rcl_now = datetime.now(dt_timezone.utc)
    assert summary['stopped'] == 'window_closed'
    assert end < utc(at(6, 0))
    assert night.mono_at - 1000.0 <= 40   # ostatnie zapytanie wyszło najpóźniej 40 s po 05:58:50, czyli przed 05:59:30


def test_run_night_obeys_robots_disallow(night):
    night.script['https://legislacja.rcl.gov.pl/robots.txt'] = ok_response(fixture_text('robots_disallow_all.txt'))
    with freeze_time(utc(at(2))) as freezer:
        clock = Clock(freezer)
        summary = harvest.run_night(sleep=clock.sleep, monotonic=clock.monotonic)
    assert summary['stopped'] == 'robots_disallowed' and night.calls == ['https://legislacja.rcl.gov.pl/robots.txt']
    assert not LegislativeProject.objects.exists()


def test_recon_mode_is_small_and_dumps_raw_pages(night, tmp_path):
    with freeze_time(utc(at(2))) as freezer:
        clock = Clock(freezer)
        summary = harvest.run_night(recon=True, budget=30, dump_dir=tmp_path, sleep=clock.sleep, monotonic=clock.monotonic)
    assert summary['requests'] <= 30 and summary['counters']['projects_refreshed'] <= 4
    assert summary['folder_names']                       # inwentarz nazw folderów do porównania z fixtures
    index = (tmp_path / 'index.tsv').read_text(encoding='utf-8').splitlines()
    assert len(index) == len(list(tmp_path.glob('*.html'))) and all('legislacja.rcl.gov.pl' in line for line in index)


def test_dry_run_uses_fixtures_without_network_and_writes_nothing(db, no_network):  # noqa: F811
    summary = harvest.dry_run()
    assert summary['status'] == 'dry_run' and summary['requests'] > 0
    assert summary['would_store']['projects'] == 4 and summary['would_store']['documents'] > 0
    assert LegislativeProject.objects.count() == 0 and LegislativeChange.objects.count() == 0
    assert not no_network


def test_files_step_is_off_by_default_and_downloads_pdfs_when_enabled(night, project, tmp_path, monkeypatch):
    harvest.refresh_project(Scripted(), harvest.Run(), project)
    pdf = b'%PDF-1.4 test'
    url = LegislativeDocument.objects.get(rcl_doc_id=795001).file_url
    night.script[url] = ok_response(pdf)
    with freeze_time(utc(at(2))) as freezer:
        clock = Clock(freezer)
        from scraper.rcl_client import RclClient
        source, card = harvest.configured_access()
        client = RclClient(source, card, sleep=clock.sleep, monotonic=clock.monotonic)
        harvest.fetch_files(client, harvest.Run(), 10)
        assert client.requests_made == 0                     # RCL_FILES_ENABLED wyłączone
        monkeypatch.setenv('RCL_FILES_ENABLED', 'true')
        monkeypatch.setenv('RCL_FILES_DIR', str(tmp_path))
        run = harvest.Run()
        harvest.fetch_files(client, run, 10)
    doc = LegislativeDocument.objects.get(rcl_doc_id=795001)
    assert doc.file_sha256 == hashlib.sha256(pdf).hexdigest() and doc.file_size == len(pdf) and doc.file_fetched_at
    assert (tmp_path / str(PROJECT) / '795001.pdf').read_bytes() == pdf
    assert run.counters['files_fetched'] == 1 and url in night.calls
