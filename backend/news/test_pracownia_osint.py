import pytest

from news import pracownia_osint as po
from news.agent_models import AgentNote

pytestmark = pytest.mark.django_db


@pytest.fixture
def quiet(monkeypatch):
    monkeypatch.setattr('news.agents_common.notify', lambda note: True)


def answers(monkeypatch, *rows):
    it = iter(rows)
    monkeypatch.setattr('news.agents_common.ask_any', lambda *a, **k: (next(it), ('groq', 'a')))


def test_catalog_ids_unique_and_statuses_valid():
    ids = [f[0] for f in po.FEATURES]
    assert len(ids) == len(set(ids))
    assert {f[3] for f in po.FEATURES} <= {'jest', 'częściowo', 'brak'} and {f[4] for f in po.FEATURES} <= {'darmowe', 'Pro'}


def test_kartograf_keeps_only_sourced_checked_gaps(quiet, monkeypatch):
    monkeypatch.setattr(po, 'feed_items', lambda: [{'source': 'GIJN', 'title': 'Alerts', 'url': 'https://gijn.org/a', 'summary': ''}])
    answers(monkeypatch,
            {'summary': 'S', 'gaps': [{'feature': 'Alerty', 'who_has': 'Aleph', 'why_journalists_care': 'czas', 'source_url': 'https://gijn.org/a'},
                                      {'feature': 'Zmyślone', 'who_has': '-', 'why_journalists_care': '-', 'source_url': 'https://inne.pl'},
                                      {'feature': 'Graf', 'who_has': 'Maltego', 'why_journalists_care': 'x', 'source_url': 'https://gijn.org/a'}]},
            {'remove': [1], 'reason': 'graf już w katalogu'})
    note = po.kartograf(force=True)
    assert [g['feature'] for g in note.scores['gaps']] == ['Alerty'] and note.kind == 'finding'


def test_zwiadowca_takes_license_from_catalog_not_model(quiet, monkeypatch):
    monkeypatch.setattr(po, 'datasets', lambda: [{'title': 'Umowy', 'url': 'https://dane.gov.pl/pl/datasets/1', 'license': 'CC0 1.0',
                                                  'modified': '2026-10-01', 'frequency': 'daily', 'source': 'MF', 'query': 'umowy'}])
    answers(monkeypatch, {'summary': 'S', 'sources': [{'dataset': 'Umowy', 'url': 'https://dane.gov.pl/pl/datasets/1', 'license': 'CC BY-NC',
                                                       'use': 'umowy przy spółkach', 'value': 9}]}, {'remove': [], 'reason': 'ok'})
    note = po.zwiadowca(force=True)
    assert note.scores['sources'][0]['license'] == 'CC0 1.0'


def test_prawnik_reviews_new_proposals_once_and_defaults_to_consultation(quiet, monkeypatch):
    AgentNote.objects.create(agent='kartograf', kind='finding', title='L', body='',
                             scores={'gaps': [{'feature': 'Alerty', 'why_journalists_care': 'czas'}, {'feature': 'Scraping FB', 'why_journalists_care': 'x'}]})
    answers(monkeypatch, {'verdicts': [{'n': 1, 'verdict': 'niedozwolone', 'why': 'obchodzi logowanie'}]})
    note = po.prawnik(force=True)
    verdicts = [r['verdict'] for r in note.scores['verdicts']]
    assert verdicts == ['do konsultacji', 'niedozwolone'] and '1 odrzuconych' in note.title
    assert not po.due('prawnik') and po.prawnik(force=True) is None


def test_kontroler_reports_missing_data_without_ai(quiet, monkeypatch):
    monkeypatch.setattr('news.agents_common.ask_any', lambda *a, **k: pytest.fail('kontroler nie pyta modeli'))
    note = po.kontroler()
    assert note.kind == 'audit' and any('głosów imiennych' in p for p in note.scores['problems'])


def test_architekt_plan_creates_ideas_and_step_survives_failures(quiet, monkeypatch):
    item = {'title': 'Głosowania imienne w temacie', 'catalog_id': 'glosowania-imienne', 'tier': 'darmowe', 'effort': 'M', 'value': 9,
            'why': 'testy dziennikarzy', 'acceptance': ['kluby zbiorczo'], 'brief': 'Zbuduj...'}
    answers(monkeypatch, {'summary': 'Plan', 'items': [item, {**item, 'title': 'Scraping'}]}, {'remove': [1], 'reason': 'nielegalne'})
    report = po.architekt(force=True)
    assert [i['title'] for i in report.scores['items']] == ['Głosowania imienne w temacie']
    assert AgentNote.objects.filter(agent='architekt', kind='idea', score=90).count() == 1

    def boom(force=False):
        raise RuntimeError('x')
    monkeypatch.setattr(po, 'ORDER', [('kartograf', boom), ('kontroler', po.kontroler)])
    done = po.step(force=True)
    assert done['kartograf'].startswith('błąd') and isinstance(done['kontroler'], int)


def test_wynalazca_keeps_checked_new_ideas_and_prawnik_sees_them(quiet, monkeypatch):
    idea = {'title': 'Licznik obietnic', 'what': 'zestawia zapowiedzi z głosowaniami', 'why_unique': 'nikt nie łączy wpisów z głosami',
            'data_used': ['Wpisy polityków z X'], 'example': 'VAT', 'tier': 'darmowe', 'wow': 9}
    answers(monkeypatch, {'summary': 'S', 'ideas': [idea, {**idea, 'title': 'Zwykła wyszukiwarka', 'wow': 3}]},
            {'remove': [1], 'reason': 'konkurencja ma'})
    note = po.wynalazca(force=True)
    assert [i['title'] for i in note.scores['ideas']] == ['Licznik obietnic'] and note.kind == 'finding'
    assert note.scores is not None and po.due('prawnik')
    answers(monkeypatch, {'verdicts': [{'n': 0, 'verdict': 'dozwolone', 'why': 'dane publiczne'}]})
    review = po.prawnik(force=True)
    assert review.scores['verdicts'][0]['what'].startswith('Pomysł: Licznik obietnic')


def test_technolog_and_orders_command(quiet, monkeypatch):
    from io import StringIO
    from django.core.management import call_command
    monkeypatch.setattr(po, 'feed_items', lambda **k: [{'source': 'spaCy', 'title': 'v4', 'url': 'https://github.com/x', 'summary': ''}])
    answers(monkeypatch, {'summary': 'S', 'tech': [{'tool': 'spaCy', 'what': 'NER', 'use_here': 'osoby w dokumentach', 'license': 'MIT',
                                                    'effort': 'M', 'value': 8, 'source_url': 'https://github.com/x'}]}, {'remove': [], 'reason': 'ok'})
    assert po.technolog(force=True).scores['tech'][0]['tool'] == 'spaCy'
    AgentNote.objects.create(agent='architekt', kind='idea', title='przeszłość.today: Profil osoby', body='', score=80,
                             scores={'tier': 'darmowe', 'effort': 'M', 'value': 8, 'why': 'testy', 'acceptance': ['funkcje KRS'], 'brief': 'Zbuduj'})
    out = StringIO()
    call_command('pracownia_zlecenia', stdout=out)
    assert 'Profil osoby' in out.getvalue() and 'odbiór: funkcje KRS' in out.getvalue()
