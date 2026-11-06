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
    base = dict(organisation_name='Fundacja Akademia Przyszłości', krs_number='', source_url='https://portal.example/a', source_title='Tytuł',
                outlet='Portal', published_on='2026-10-01', quote='Dosłowny cytat.', category='alleged')
    base.update(kw)
    return base


def test_item_goes_to_review_queue_only_with_link_from_search_results_and_org_in_db(monkeypatch):
    f, o = figure(), org('Fundacja Akademia Przyszłości', '0000000111')
    resp = fake_response([item(), item(source_url='https://wymyslony.example/x'), item(organisation_name='Fundacja Spoza Bazy')])
    monkeypatch.setattr(clinic_ai, '_call_claude', lambda *a, **k: resp)
    by_krs, by_name = db.org_lookup()
    stats, cost, outside = db.research_person(f, by_krs, by_name, apply=True)
    assert stats['saved'] == 1 and stats['dropped_url'] == 1 and stats['outside_db'] == 1 and outside == ['Fundacja Spoza Bazy [brak numeru KRS]'] and cost > 0
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


def _extract(name='FUNDACJA PROFETO', number='0000012345'):
    return NS(name=name, krs=number)


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
    resp = fake_response([item(organisation_name='Fundacja Profeto', krs_number='0000012345'),
                          item(organisation_name='Zupełnie Inna Nazwa', krs_number='0000099999', source_url='https://portal.example/b')],
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
    monkeypatch.setattr(clinic_ai, '_call_claude', lambda *a, **k: fake_response([item(organisation_name='Fundacja Profeto', krs_number='0000012345')]))
    by_krs, by_name = db.org_lookup()
    stats, _, _ = db.research_person(f, by_krs, by_name, apply=False)
    assert stats['org_added'] == 1 and stats['saved'] == 1
    assert RegisteredOrganisation.objects.count() == 0 and PublicFigureMediaMention.objects.count() == 0


def test_no_krs_number_means_outside_db_without_registry_call(monkeypatch):
    from news import krs
    f = figure()
    monkeypatch.setattr(krs, 'fetch_status', lambda *a, **k: (_ for _ in ()).throw(AssertionError('bez numeru nie pytamy KRS')))
    monkeypatch.setattr(clinic_ai, '_call_claude', lambda *a, **k: fake_response([item(organisation_name='Fundacja Profeto', krs_number='')]))
    by_krs, by_name = db.org_lookup()
    stats, _, outside = db.research_person(f, by_krs, by_name, apply=True)
    assert stats['outside_db'] == 1 and 'brak numeru KRS' in outside[0]


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
