import json
from types import SimpleNamespace as NS

import pytest

from news import clinic_ai, doniesienia_lejek as lj
from news.media_mentions import name_pattern
from news.models import Article, Source
from news.political_models import MediaResearchLog, PublicFigure, PublicFigureMediaMention, RegisteredOrganisation
from django.utils import timezone

pytestmark = pytest.mark.django_db

HTML = ('<html><head><title>x</title><script>var a=1;</script></head><body><nav>Menu Fundacja Menu</nav><article>'
        '<p>Poseł Jan Kowalski był gościem programu.</p><p>Według doniesień Jan Kowalski współpracuje z Fundacją Akademia Przyszłości, '
        'która otrzymała dotację z ministerstwa.</p></article><footer>stopka</footer></body></html>')


def figure():
    return PublicFigure.objects.create(canonical_name='Jan Kowalski', role_category='parliamentary', role_title='Poseł')


def org():
    return RegisteredOrganisation.objects.create(name='Fundacja Akademia Przyszłości', krs_number='0000000111', kind='foundation',
                                                 official_register_url='https://ekrs.ms.gov.pl/x')


def test_html_to_text_skips_scripts_nav_and_footer():
    text = lj.html_to_text(HTML)
    assert 'var a' not in text and 'Menu' not in text and 'stopka' not in text and 'Jan Kowalski' in text


def test_excerpts_need_full_name_and_a_trigger_word():
    person = name_pattern('Jan Kowalski')
    text = lj.html_to_text(HTML)
    assert 'Fundacją Akademia Przyszłości' in lj.excerpts(text, person)
    assert lj.excerpts('Jan Kowalski poszedł na spacer w parku i wrócił do domu.', person) == ''
    assert lj.excerpts('Fundacja coś robi, a Anna Nowak nic.', person) == ''


def test_verify_requires_literal_quote_and_org_name_in_that_article_excerpt():
    arts = [{'url': 'https://m.example/1', 'title': 'T', 'outlet': 'm.example', 'date': '2026-10-01',
             'excerpt': 'Według doniesień Jan Kowalski współpracuje z Fundacją Akademia Przyszłości, która otrzymała dotację.'}]
    good = {'article': 0, 'organisation_name': 'Fundacją Akademia Przyszłości', 'quote': 'Jan Kowalski współpracuje z Fundacją Akademia Przyszłości'}
    made_up = {'article': 0, 'organisation_name': 'Fundacja Akademia Przyszłości', 'quote': 'Jan Kowalski założył tę fundację w 2015 roku'}
    wrong_index = {**good, 'article': 3}
    kept, dropped = lj.verify([good, made_up, wrong_index], arts)
    assert len(kept) == 1 and dropped == 2 and kept[0]['source_url'] == 'https://m.example/1' and kept[0]['published_on'] == '2026-10-01'


def test_gdelt_parsing_and_failure_modes():
    ok = NS(json=lambda: {'articles': [{'url': 'https://m.example/a', 'title': 'Tytuł', 'domain': 'm.example', 'seendate': '20261105T123000Z'}]})
    assert lj.gdelt_articles('Jan Kowalski', get=lambda *a, **k: ok) == [{'url': 'https://m.example/a', 'title': 'Tytuł', 'outlet': 'm.example', 'date': '2026-11-05'}]
    bad = NS(json=lambda: (_ for _ in ()).throw(ValueError('To nie JSON')))
    assert lj.gdelt_articles('Jan Kowalski', get=lambda *a, **k: bad) == []


def test_fetch_respects_publisher_refusals_and_robots(monkeypatch):
    from scraper import media_metadata
    monkeypatch.setattr(media_metadata, '_known', lambda url: 'rejestr zgód: wymaga zgody wydawcy')
    assert lj.fetch_text('https://zablokowany.example/a', get=lambda *a, **k: (_ for _ in ()).throw(AssertionError('bez pobrania')))[1].startswith('rejestr zgód')
    monkeypatch.setattr(media_metadata, '_known', lambda url: '')
    monkeypatch.setattr(media_metadata, 'tdm_allows', lambda url, network=None: {'ok': False, 'reason': 'robots_disallowed'})
    assert lj.fetch_text('https://m.example/a', get=lambda *a, **k: (_ for _ in ()).throw(AssertionError('bez pobrania')))[1] == 'robots_disallowed'


def test_full_funnel_saves_verified_item_to_review_queue_only(monkeypatch):
    from scraper import media_metadata
    f, o = figure(), org()
    monkeypatch.setattr(media_metadata, '_known', lambda url: '')
    monkeypatch.setattr(media_metadata, 'tdm_allows', lambda url, network=None: {'ok': True, 'reason': ''})
    monkeypatch.setattr(lj.time, 'sleep', lambda s: None)
    monkeypatch.setattr(lj, 'gdelt_articles', lambda name, **k: [{'url': 'https://m.example/a', 'title': 'Tytuł artykułu', 'outlet': 'm.example', 'date': '2026-10-01'}])
    monkeypatch.setattr(lj, 'fetch_text', lambda url, get=None: (lj.html_to_text(HTML), ''))
    items = [{'article': 0, 'organisation_name': 'Fundacja Akademia Przyszłości', 'krs_number': '', 'city': '', 'board_member': '', 'category': 'alleged',
              'quote': 'Jan Kowalski współpracuje z Fundacją Akademia Przyszłości, która otrzymała dotację'},
             {'article': 0, 'organisation_name': 'Fundacja Wymyślona', 'krs_number': '', 'city': '', 'board_member': '', 'category': 'alleged',
              'quote': 'cytat, którego nie ma w tekście artykułu wcale'}]
    monkeypatch.setattr(lj, 'extract', lambda figure_, articles: (items, 0.002))
    by_krs, by_name = lj.db.org_lookup()
    stats, cost, outside = lj.research_person_funnel(f, by_krs, by_name, apply=True)
    assert stats['saved'] == 1 and stats['dropped_quote'] == 1 and cost == 0.002
    m = PublicFigureMediaMention.objects.get()
    assert (m.status, m.collected_by, m.category, m.organisation_id, m.source_url) == ('pending_review', 'lejek', 'alleged', o.pk, 'https://m.example/a')


def test_run_logs_person_and_stops_on_budget(monkeypatch):
    f = figure()
    monkeypatch.setattr(lj, 'research_person_funnel', lambda *a, **k: ({'candidates': 3, 'fetched': 2, 'excerpts': 1, 'items': 1, 'saved': 1, 'dropped_quote': 0, 'outside_db': 0, 'org_added': 0}, 0.5, []))
    out = []
    result = lj.run(ids=[f.pk], apply=True, budget_usd=0.4, write=out.append)
    assert result['persons'] == 1 and MediaResearchLog.objects.filter(public_figure=f).count() == 1
    assert lj.run(ids=[f.pk], apply=True, budget_usd=0.4, write=out.append)['persons'] == 0   # zbadana: pomijana


def test_org_name_is_matched_in_inflected_form_but_not_when_a_word_is_missing():
    text = lj._norm('współpracuje z Fundacją Akademią Przyszłości, która')
    assert lj.name_in_text('Fundacja Akademia Przyszłości', text)
    assert not lj.name_in_text('Fundacja Akademia Rozwoju', text)
    assert not lj.name_in_text('', text)
