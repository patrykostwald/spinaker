import json
from types import SimpleNamespace as NS

import pytest
from django.core.management import call_command

from news import clinic_ai, doniesienia_badacz as db
from news.political_models import PublicFigure, PublicFigureMediaMention, RegisteredOrganisation

pytestmark = pytest.mark.django_db


def figure(name='Jan Kowalski', **kw):
    return PublicFigure.objects.create(canonical_name=name, role_category='parliamentary', role_title='Poseł', **kw)


def org(name, krs):
    return RegisteredOrganisation.objects.create(name=name, krs_number=krs, kind='foundation', official_register_url='https://ekrs.ms.gov.pl/x')


def fake_response(items, urls=('https://portal.example/a',)):
    results = [NS(url=u, title='T ' + u) for u in urls]
    blocks = [NS(type='web_search_tool_result', content=results), NS(type='text', text=json.dumps({'items': items}))]
    usage = NS(input_tokens=20000, output_tokens=2000, server_tool_use=NS(web_search_requests=4))
    return NS(content=blocks, usage=usage, model='claude-sonnet-5', stop_reason='end_turn')


def item(**kw):
    base = dict(organisation_name='Fundacja Akademia Przyszłości', krs_number='', city='', board_member='', source_url='https://portal.example/a', source_title='Tytuł',
                outlet='Portal', published_on='2026-10-01', quote='Dosłowny cytat.', category='alleged')
    base.update(kw)
    return base


def test_item_goes_to_review_queue_only_with_link_from_search_results_and_org_in_db(monkeypatch):
    f, o = figure(), org('Fundacja Akademia Przyszłości', '0000000111')
    resp = fake_response([item(), item(source_url='https://wymyslony.example/x'), item(organisation_name='Fundacja Spoza Bazy')])
    monkeypatch.setattr(clinic_ai, '_call_claude', lambda *a, **k: resp)
    by_krs, by_name = db.org_lookup()
    stats, cost, outside = db.research_person(f, by_krs, by_name, apply=True)
    assert stats['saved'] == 1 and stats['dropped_url'] == 1 and stats['outside_db'] == 1 and len(outside) == 1 and outside[0].startswith('Fundacja Spoza Bazy [brak numeru KRS i drugiej danej') and cost > 0
    m = PublicFigureMediaMention.objects.get()
    assert (m.status, m.collected_by, m.match_basis, m.category, m.organisation_id) == ('pending_review', 'claude', 'name_only', 'alleged', o.pk)


def test_krs_from_answer_gives_identifier_basis_and_dry_run_writes_nothing(monkeypatch):
    f = figure()
    o = org('Fundacja Akademia Przyszłości', '0000000111')
    monkeypatch.setattr(clinic_ai, '_call_claude', lambda *a, **k: fake_response([item(organisation_name='Inna nazwa', krs_number='111')]))
    by_krs, by_name = db.org_lookup()
    stats, _, _ = db.research_person(f, by_krs, by_name, apply=False)
    assert stats['saved'] == 1 and PublicFigureMediaMention.objects.count() == 0
    db.research_person(f, by_krs, by_name, apply=True)
    assert PublicFigureMediaMention.objects.get().match_basis == 'identifier' and PublicFigureMediaMention.objects.get().organisation_id == o.pk


def test_budget_stops_the_run_and_ambiguous_names_are_not_matched(monkeypatch):
    figure('Jan Kowalski'); figure('Anna Nowak', import_key='n')
    org('Fundacja Akademia Przyszłości', '0000000111'); org('Fundacja Akademia Przyszłości', '0000000112')   # ta sama nazwa: niejednoznaczna
    monkeypatch.setattr(clinic_ai, '_call_claude', lambda *a, **k: fake_response([item()]))
    out = []
    result = db.run(names=['Jan Kowalski', 'Anna Nowak'], apply=True, budget_usd=0.001, pause=0, write=out.append)
    assert result['persons'] == 1 and any('LIMIT KOSZTU' in line for line in out)
    assert PublicFigureMediaMention.objects.count() == 0 and result['outside_db'] == 1


def test_estimate_command_makes_no_paid_call(monkeypatch, capsys):
    figure()
    def boom(*a, **k):
        raise AssertionError('płatne wywołanie przy --szacuj')
    monkeypatch.setattr(clinic_ai, '_call_claude', boom)
    call_command('przeszlosc_doniesienia_badaj', '--szacuj', '--osoba', str(PublicFigure.objects.get().pk))
    assert 'Nic nie wysłano' in capsys.readouterr().out


def test_schema_uses_only_keywords_accepted_by_structured_outputs():
    """Produkcja odrzuciła 'maxItems' (400: property 'maxItems' is not supported); limit pozycji pilnuje kod, nie schemat."""
    text = json.dumps(db.SCHEMA)
    for forbidden in ('maxItems', 'minItems', 'maxLength', 'minLength', 'minimum', 'maximum'):
        assert forbidden not in text


def test_more_items_than_the_limit_are_cut_in_code(monkeypatch):
    f = figure()
    org('Fundacja Akademia Przyszłości', '0000000111')
    many = [item(source_url=f'https://portal.example/{i}') for i in range(db.PER_PERSON_ITEMS + 4)]
    urls = tuple(f'https://portal.example/{i}' for i in range(db.PER_PERSON_ITEMS + 4))
    monkeypatch.setattr(clinic_ai, '_call_claude', lambda *a, **k: fake_response(many, urls))
    by_krs, by_name = db.org_lookup()
    stats, _, _ = db.research_person(f, by_krs, by_name, apply=True)
    assert stats['items'] == db.PER_PERSON_ITEMS and PublicFigureMediaMention.objects.count() == db.PER_PERSON_ITEMS


def test_light_settings_apply_only_during_the_call(monkeypatch):
    import os
    seen = {}
    f = figure()
    monkeypatch.setenv('CLINIC_EFFORT', 'high')
    monkeypatch.delenv('CLINIC_WEB_SEARCH_MAX_USES', raising=False)

    def fake(*a, **k):
        seen.update(effort=os.environ['CLINIC_EFFORT'], uses=os.environ['CLINIC_WEB_SEARCH_MAX_USES'])
        return fake_response([])
    monkeypatch.setattr(clinic_ai, '_call_claude', fake)
    db.research_person(f, {}, {}, apply=False)
    assert seen == {'effort': 'low', 'uses': '4'}
    assert os.environ['CLINIC_EFFORT'] == 'high' and 'CLINIC_WEB_SEARCH_MAX_USES' not in os.environ


def _extract(name='FUNDACJA PROFETO', number='0000012345', city='WARSZAWA', persons=()):
    return NS(name=name, krs=number, seat_city=city, persons=list(persons))


def test_org_outside_db_is_adopted_only_after_krs_registry_confirms_the_name(monkeypatch):
    from news import krs, krs_pokrycie
    f = figure()
    monkeypatch.setattr(db.time, 'sleep', lambda s: None)
    monkeypatch.setattr(krs, 'fetch_status', lambda number, full=False, timeout=30: (_extract('FUNDACJA PROFETO', number), 'ok'))
    created = []
    def fake_save(extract):
        o = org('Fundacja Profeto', extract.krs)
        created.append(o.pk)
        return o
    monkeypatch.setattr(krs_pokrycie, 'save_extract', fake_save)
    resp = fake_response([item(organisation_name='Fundacja Profeto', krs_number='0000012345', city='Warszawa'),
                          item(organisation_name='Zupełnie Inna Nazwa', krs_number='0000099999', city='Warszawa', source_url='https://portal.example/b')],
                         urls=('https://portal.example/a', 'https://portal.example/b'))
    monkeypatch.setattr(clinic_ai, '_call_claude', lambda *a, **k: resp)
    by_krs, by_name = db.org_lookup()
    stats, _, outside = db.research_person(f, by_krs, by_name, apply=True)
    assert stats['org_added'] == 1 and stats['saved'] == 1 and created and stats['outside_db'] == 1
    assert 'nazwa niezgodna z odpisem KRS' in outside[0] and PublicFigureMediaMention.objects.get().organisation.krs_number == '0000012345'


def test_dry_run_checks_krs_but_creates_nothing(monkeypatch):
    from news import krs
    f = figure()
    monkeypatch.setattr(db.time, 'sleep', lambda s: None)
    monkeypatch.setattr(krs, 'fetch_status', lambda number, full=False, timeout=30: (_extract(), 'ok'))
    monkeypatch.setattr(clinic_ai, '_call_claude', lambda *a, **k: fake_response([item(organisation_name='Fundacja Profeto', krs_number='0000012345', city='Warszawa')]))
    by_krs, by_name = db.org_lookup()
    stats, _, _ = db.research_person(f, by_krs, by_name, apply=False)
    assert stats['org_added'] == 1 and stats['saved'] == 1
    assert RegisteredOrganisation.objects.count() == 0 and PublicFigureMediaMention.objects.count() == 0


def test_no_krs_number_means_outside_db_without_registry_call(monkeypatch):
    from news import krs
    f = figure()
    monkeypatch.setattr(krs, 'fetch_status', lambda *a, **k: (_ for _ in ()).throw(AssertionError('bez numeru nie pytamy KRS')))
    monkeypatch.setattr(clinic_ai, '_call_claude', lambda *a, **k: fake_response([item(organisation_name='Fundacja Profeto', krs_number='', city='')]))
    by_krs, by_name = db.org_lookup()
    stats, _, outside = db.research_person(f, by_krs, by_name, apply=True)
    assert stats['outside_db'] == 1 and 'brak numeru KRS' in outside[0] and 'miejscowość: -' in outside[0]


def test_researched_person_is_logged_and_skipped_next_time(monkeypatch):
    from news.political_models import MediaResearchLog
    f = figure()
    org('Fundacja Akademia Przyszłości', '0000000111')
    monkeypatch.setattr(clinic_ai, '_call_claude', lambda *a, **k: fake_response([item()]))
    out = []
    db.run(ids=[f.pk], apply=True, pause=0, write=out.append)
    log = MediaResearchLog.objects.get()
    assert log.public_figure_id == f.pk and log.saved == 1 and log.cost_usd > 0
    assert db.pick_figures(ids=[f.pk]) == []                         # zbadana: pomijana
    assert [x.pk for x in db.pick_figures(ids=[f.pk], skip_days=0)] == [f.pk]   # --ponow
    db.run(ids=[f.pk], apply=False, pause=0, write=out.append)
    assert MediaResearchLog.objects.count() == 1                      # raport bez zapisu nie loguje


def test_dry_run_does_not_mark_person_as_researched(monkeypatch):
    from news.political_models import MediaResearchLog
    f = figure()
    monkeypatch.setattr(clinic_ai, '_call_claude', lambda *a, **k: fake_response([]))
    db.run(ids=[f.pk], apply=False, pause=0, write=lambda x: None)
    assert MediaResearchLog.objects.count() == 0 and [x.pk for x in db.pick_figures(ids=[f.pk])] == [f.pk]


def test_everyone_mode_orders_government_first_skips_parties_and_researched(monkeypatch):
    from news.political_models import MediaResearchLog
    a = PublicFigure.objects.create(canonical_name='Anna Parlament', role_category='parliamentary', role_title='Posłanka', import_key='a')
    b = PublicFigure.objects.create(canonical_name='Piotr Rząd', role_category='government', role_title='Minister', import_key='b')
    PublicFigure.objects.create(canonical_name='Partia Testowa', role_category='party', role_title='Partia', import_key='p')
    done = PublicFigure.objects.create(canonical_name='Ewa Zbadana', role_category='government', role_title='Minister', import_key='c')
    MediaResearchLog.objects.create(public_figure=done)
    assert [f.pk for f in db.pick_figures(everyone=True)] == [b.pk, a.pk]
    assert [f.pk for f in db.pick_figures(everyone=True, limit=1)] == [b.pk]


def test_lobbying_category_is_accepted_and_saved(monkeypatch):
    f = figure()
    org('Fundacja Akademia Przyszłości', '0000000111')
    monkeypatch.setattr(clinic_ai, '_call_claude', lambda *a, **k: fake_response([item(category='lobbying')]))
    by_krs, by_name = db.org_lookup()
    db.research_person(f, by_krs, by_name, apply=True)
    assert PublicFigureMediaMention.objects.get().category == 'lobbying'


def test_second_datum_is_required_and_must_match_the_registry(monkeypatch):
    from news import krs
    monkeypatch.setattr(db.time, 'sleep', lambda s: None)
    monkeypatch.setattr(krs, 'fetch_status', lambda number, full=False, timeout=30: (_extract('FUNDACJA PROFETO', number, 'KRAKÓW'), 'ok'))
    base = dict(organisation_name='Fundacja Profeto', krs_number='0000012345', board_member='')
    assert db.verify_candidate('0000012345', {**base, 'city': ''})[1].startswith('brak drugiej danej')      # sama nazwa nie wystarcza
    assert db.verify_candidate('0000012345', {**base, 'city': 'Warszawa'})[1] == 'druga dana niezgodna z odpisem KRS'
    assert db.verify_candidate('0000012345', {**base, 'city': 'Kraków'})[1] == 'ok'


def test_board_member_matches_persons_in_the_extract(monkeypatch):
    from news import krs
    monkeypatch.setattr(db.time, 'sleep', lambda s: None)
    person = krs.Person(surname='NOWAK', first='ANNA', second='', function='PREZES', organ='ZARZĄD', since=None, until=None)
    monkeypatch.setattr(krs, 'fetch_status', lambda number, full=False, timeout=30: (_extract('FUNDACJA PROFETO', number, 'KRAKÓW', [person]), 'ok'))
    item_ = dict(organisation_name='Fundacja Profeto', city='', board_member='Anna Nowak')
    assert db.verify_candidate('0000012345', item_)[1] == 'ok'
    assert db.verify_candidate('0000012345', {**item_, 'board_member': 'Jan Kowalski'})[1] == 'druga dana niezgodna z odpisem KRS'


def test_second_round_finds_number_for_org_without_krs_and_verifies_it(monkeypatch):
    from news import krs, krs_pokrycie
    f = figure()
    monkeypatch.setattr(db.time, 'sleep', lambda s: None)
    calls = []
    def fake_light(system, user, schema=None, searches=None, max_tokens=0):
        calls.append(schema is db.FIND_SCHEMA)
        return NS(content=[NS(type='text', text=json.dumps({'krs_number': '0000012345'}))]), 0.02
    monkeypatch.setattr(db, '_light_call', fake_light)
    monkeypatch.setattr(clinic_ai, '_call_claude', lambda *a, **k: fake_response([item(organisation_name='Fundacja Profeto', krs_number='', city='Warszawa')]))
    monkeypatch.setattr(krs, 'fetch_status', lambda number, full=False, timeout=30: (_extract('FUNDACJA PROFETO', number, 'WARSZAWA'), 'ok'))
    monkeypatch.setattr(krs_pokrycie, 'save_extract', lambda extract: org('Fundacja Profeto', extract.krs))
    by_krs, by_name = db.org_lookup()
    stats, cost, _ = db.research_person(f, by_krs, by_name, apply=True)
    assert calls == [True] and stats['org_added'] == 1 and stats['saved'] == 1 and cost > 0
    assert PublicFigureMediaMention.objects.get().organisation.krs_number == '0000012345'


def test_same_org_from_two_articles_is_resolved_once(monkeypatch):
    from news import krs, krs_pokrycie
    f = figure()
    monkeypatch.setattr(db.time, 'sleep', lambda s: None)
    calls = []
    monkeypatch.setattr(db, '_light_call', lambda *a, **k: (calls.append(1), (NS(content=[NS(type='text', text=json.dumps({'krs_number': '0000012345'}))]), 0.02))[1])
    two = [item(organisation_name='Fundacja Profeto', krs_number='', city='Warszawa', source_url='https://portal.example/a'),
           item(organisation_name='Fundacja Profeto', krs_number='', city='Warszawa', source_url='https://portal.example/b')]
    monkeypatch.setattr(clinic_ai, '_call_claude', lambda *a, **k: fake_response(two, urls=('https://portal.example/a', 'https://portal.example/b')))
    monkeypatch.setattr(krs, 'fetch_status', lambda number, full=False, timeout=30: (_extract('FUNDACJA PROFETO', number, 'WARSZAWA'), 'ok'))
    monkeypatch.setattr(krs_pokrycie, 'save_extract', lambda extract: RegisteredOrganisation.objects.get_or_create(krs_number=extract.krs, defaults={'name': 'Fundacja Profeto', 'kind': 'foundation', 'official_register_url': 'https://ekrs.ms.gov.pl/x'})[0])
    by_krs, by_name = db.org_lookup()
    stats, _, _ = db.research_person(f, by_krs, by_name, apply=True)
    assert len(calls) == 1 and stats['saved'] == 2 and PublicFigureMediaMention.objects.count() == 2


def test_no_second_round_without_second_datum(monkeypatch):
    f = figure()
    calls = []
    monkeypatch.setattr(clinic_ai, '_call_claude', lambda *a, **k: (calls.append(1), fake_response([item(organisation_name='Fundacja Profeto')]))[1])
    by_krs, by_name = db.org_lookup()
    stats, _, outside = db.research_person(f, by_krs, by_name, apply=True)
    assert len(calls) == 1 and stats['outside_db'] == 1 and 'brak numeru KRS' in outside[0]


def _light_response(items, urls=('https://portal.example/a',), searches=2, stop='end_turn'):
    results = [NS(url=u, title='T ' + u) for u in urls]
    blocks = [NS(type='web_search_tool_result', content=results), NS(type='text', text=json.dumps({'items': items}))]
    return NS(content=blocks, stop_reason=stop, usage=NS(input_tokens=30000, output_tokens=800, server_tool_use=NS(web_search_requests=searches)), model='claude-haiku-5-5')


class _FakeClient:
    def __init__(self, responses, record):
        self.responses, self.record = list(responses), record
        self.messages = NS(create=self._create)

    def _create(self, **kwargs):
        self.record.append(kwargs)
        return self.responses.pop(0)


def test_light_researcher_uses_cheap_model_basic_search_tool_and_same_safeguards(monkeypatch):
    f, o = figure(), org('Fundacja Akademia Przyszłości', '0000000111')
    record = []
    monkeypatch.setattr(clinic_ai, '_client', lambda: _FakeClient([_light_response([item(), item(source_url='https://wymyslony.example/x')])], record))
    by_krs, by_name = db.org_lookup()
    stats, cost, _ = db.research_person_light(f, by_krs, by_name, apply=True)
    assert record[0]['model'] == 'claude-haiku-5-5' and record[0]['tools'][0]['type'] == 'web_search_20250305' and record[0]['tools'][0]['max_uses'] == 3
    assert stats['saved'] == 1 and stats['dropped_url'] == 1 and PublicFigureMediaMention.objects.get().organisation_id == o.pk
    assert 0.02 < cost < 0.05          # 30 tys. tokenów wejścia Haiku + 2 wyszukiwania


def test_light_researcher_resumes_pause_turn_and_falls_back_when_structured_output_is_rejected(monkeypatch):
    import anthropic
    f, o = figure(), org('Fundacja Akademia Przyszłości', '0000000111')
    record = []
    bad = anthropic.BadRequestError.__new__(anthropic.BadRequestError)   # bez budowania odpowiedzi HTTP (zależy od wersji SDK)
    bad.body, bad.message, bad.status_code = {'error': {'message': 'format nie łączy się z narzędziem'}}, 'x', 400

    class Client(_FakeClient):
        def _create(self, **kwargs):
            self.record.append(kwargs)
            first = self.responses.pop(0)
            if isinstance(first, Exception):
                raise first
            return first
    monkeypatch.setattr(clinic_ai, '_client', lambda: Client([bad, _light_response([], stop='pause_turn'), _light_response([item()])], record))
    by_krs, by_name = db.org_lookup()
    stats, _, _ = db.research_person_light(f, by_krs, by_name, apply=False)
    assert 'format' in record[0]['output_config'] and 'format' not in record[1]['output_config'] and len(record) == 3 and stats['saved'] == 1


def test_light_flag_is_used_by_run_and_logged(monkeypatch):
    from news.political_models import MediaResearchLog
    f = figure()
    monkeypatch.setattr(db, 'research_person_light', lambda *a, **k: ({'items': 0, 'saved': 0, 'dropped_url': 0, 'outside_db': 0, 'existing': 0, 'org_added': 0}, 0.03, []))
    monkeypatch.setattr(db, 'research_person', lambda *a, **k: (_ for _ in ()).throw(AssertionError('ścieżka ciężka')))
    out = []
    db.run(ids=[f.pk], apply=True, pause=0, write=out.append, light=True)
    assert MediaResearchLog.objects.get().model.startswith('lekki:')


def test_unresolved_org_reports_why_and_which_hints_it_had(monkeypatch):
    f = figure()
    monkeypatch.setattr(db, '_light_call', lambda *a, **k: (NS(content=[NS(type='text', text=json.dumps({'krs_number': ''}))]), 0.02))
    monkeypatch.setattr(clinic_ai, '_call_claude', lambda *a, **k: fake_response([item(organisation_name='Stowarzyszenie Fidei Defensor', city='Kraków', board_member='')]))
    by_krs, by_name = db.org_lookup()
    stats, _, outside = db.research_person(f, by_krs, by_name, apply=False)
    assert stats['outside_db'] == 1 and 'nie ustalono numeru KRS' in outside[0] and 'miejscowość: Kraków' in outside[0]


def test_strict_name_match_rejects_half_matching_names_but_accepts_inflection_and_legal_forms():
    assert db.strict_name_match('Stowarzyszenie Przyjaciół Zdrowia', 'STOWARZYSZENIE PRZYJACIÓŁ ZDROWIA')
    assert not db.strict_name_match('Stowarzyszenie Przyjaciół Zdrowia', 'STOWARZYSZENIE PRZYJACIÓŁ MEDIÓW')   # błąd z produkcji (#227)
    assert db.strict_name_match('Fundacja Ośrodek Monitorowania Antypolonizmu (OMA)', 'FUNDACJA OŚRODEK MONITOROWANIA ANTYPOLONIZMU')
    assert db.strict_name_match('Fundacji Profeto', 'FUNDACJA PROFETO')
    assert not db.strict_name_match('Fundacja Polska', 'FUNDACJA POLSKA PRZEMYSŁ')    # puste po zdjęciu słów ogólnych
    assert not db.strict_name_match('', 'FUNDACJA X')


def test_registry_and_aggregator_pages_are_not_media_sources(monkeypatch):
    f, o = figure(), org('Fundacja Akademia Przyszłości', '0000000111')
    resp = fake_response([item(source_url='https://rejestr.io/krs/111/fundacja')], urls=('https://rejestr.io/krs/111/fundacja',))
    monkeypatch.setattr(clinic_ai, '_call_claude', lambda *a, **k: resp)
    by_krs, by_name = db.org_lookup()
    stats, _, _ = db.research_person(f, by_krs, by_name, apply=True)
    assert stats['dropped_url'] == 1 and PublicFigureMediaMention.objects.count() == 0
    assert db.is_registry_host('https://www.rejestr.io/x') and not db.is_registry_host('https://wiadomosci.wp.pl/a')


def test_adoption_refuses_org_whose_name_only_half_matches(monkeypatch):
    from news import krs
    monkeypatch.setattr(db.time, 'sleep', lambda s: None)
    monkeypatch.setattr(krs, 'fetch_status', lambda number, full=False, timeout=30: (_extract('STOWARZYSZENIE PRZYJACIÓŁ MEDIÓW', number, 'SZCZECIN'), 'ok'))
    wrong = dict(organisation_name='Stowarzyszenie Przyjaciół Zdrowia', krs_number='0000422794', city='Szczecin', board_member='')
    assert db.verify_candidate('0000422794', wrong)[1] == 'nazwa niezgodna z odpisem KRS'
