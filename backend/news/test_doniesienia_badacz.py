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
    assert stats['saved'] == 1 and stats['dropped_url'] == 1 and stats['outside_db'] == 1 and outside == ['Fundacja Spoza Bazy'] and cost > 0
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
