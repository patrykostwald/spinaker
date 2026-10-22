"""Jak spin zadziałał: limity budżetu X, flaga wyłączona = zero zapytań, brak danych osób prywatnych, agregacja,
ta sama miara dla każdej partii. Bez sieci i bez płatnych wywołań (odczyty X i model podmienione)."""
import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.utils import timezone

from news import odbior_spinu as od
from news.agents_common import WindowClosed
from news.clinic_models import ReceptionCheck, SpinDiagnosis
from news.models import ImportState
from news.political_polling import PoliticalReadError
from news.test_zmiana_zdania import account, figure

pytestmark = pytest.mark.django_db
POST_TEXT = 'Podatek od żywności to zamach na rodziny. Rząd okrada Polaków każdego dnia, koniec z drożyzną!'
PRIVATE = [  # (autor, id, tekst) - dane osób prywatnych, które nie mogą trafić do bazy
    ('900001', '1800000000000000001', '@jan_kowalski_77 Racja, rząd okrada Polaków, wreszcie ktoś to mówi'),
    ('900002', '1800000000000000002', 'Racja! Rząd okrada Polaków od lat https://t.co/abc123'),
    ('900003', '1800000000000000003', 'Pokaż dane, skąd te liczby? Rząd okrada Polaków to slogan'),
    ('900004', '1800000000000000004', 'Hahaha, a kto podniósł VAT? Marek z Radomia się śmieje'),
    ('900005', '1800000000000000005', 'Nieprawda, inflacja spada od pół roku'),
    ('900006', '1800000000000000006', 'Brawo, popieram w stu procentach'),
    ('900007', '1800000000000000007', 'Popieram, koniec z drożyzną'),
    ('900008', '1800000000000000008', 'Zgadzam się, koniec z drożyzną'),
    ('900009', '1800000000000000009', 'Kłamstwo, ceny żywności rosną wolniej niż rok temu'),
    ('900010', '1800000000000000010', 'Super, popieram!'),
    ('900011', '1800000000000000011', 'Jasne, popieram, koniec z drożyzną'),
]
LABELS = ['zgoda', 'zgoda', 'sprzeciw', 'kpina', 'sprzeciw', 'zgoda', 'zgoda', 'zgoda', 'sprzeciw', 'zgoda', 'zgoda']


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    cache.clear()
    for name, value in {'X_POLITICAL_POLLING_ENABLED': 'true', 'X_POLITICAL_BEARER_TOKEN': 'test-token',
                        'X_POLITICAL_MONTHLY_USD_LIMIT': '50', 'X_REPLIES_ENABLED': 'true'}.items():
        monkeypatch.setenv(name, value)
    for name in ('X_REPLIES_DAILY_CAP', 'X_REPLIES_PER_POST', 'X_REPLIES_MIN_INTENSITY', 'X_REPLIES_BUDGET_FLOOR'):
        monkeypatch.delenv(name, raising=False)
    yield
    cache.clear()


class FakeX:
    """Podmienia oba odczyty X; liczy wywołania."""
    def __init__(self, monkeypatch, replies=PRIVATE, metrics_error=None, replies_error=None, extra=()):
        self.calls = []
        self.replies = list(replies) + list(extra)

        def metrics(post, config):
            self.calls.append('metrics')
            if metrics_error:
                raise metrics_error
            return json.dumps({'data': {'id': post.post_id, 'conversation_id': post.post_id, 'author_id': post.account.user_id,
                                        'public_metrics': {'like_count': 1450, 'retweet_count': 320, 'reply_count': 610, 'quote_count': 41}}}).encode()

        def replies_fn(post, conversation_id, limit, config):
            self.calls.append('replies')
            if replies_error:
                raise replies_error
            rows = [{'id': i, 'author_id': a, 'text': t, 'conversation_id': conversation_id} for a, i, t in self.replies[:limit]]
            return json.dumps({'data': rows, 'meta': {'result_count': len(rows)}}).encode()

        monkeypatch.setattr(od, 'fetch_metrics', metrics)
        monkeypatch.setattr(od, 'fetch_replies', replies_fn)


def model(monkeypatch, labels=LABELS, fail=False):
    asked = []

    def fake(payload):
        asked.append(payload)
        if fail:
            raise WindowClosed('Brak wolnego darmowego modelu')
        return {'odpowiedzi': [{'i': i, 'stance': labels[i % len(labels)], 'tone': 'negatywny' if labels[i % len(labels)] != 'zgoda' else 'pozytywny',
                                'asks_source': 'skąd' in r['tekst'].lower()} for i, r in enumerate(payload['odpowiedzi'])]}, 'groq/test'
    monkeypatch.setattr(od, 'model_ready', lambda: True)
    monkeypatch.setattr(od, 'ask', fake)
    return asked


_seq = iter(range(10_000, 99_999))


def diagnosis(camp='government', intensity=70, hours=26, verdict='spin', handle=None):
    n = next(_seq)
    person = figure(f'Osoba {n}')
    acc = account(person, handle or f'konto{n}', str(n), camp=camp)
    from news.political_models import PoliticalPost
    post = PoliticalPost.objects.create(account=acc, post_id=str(n * 10), url=f'https://x.com/{acc.handle}/status/{n * 10}', text=POST_TEXT,
                                        published_at=timezone.now() - timedelta(hours=hours), response_sha256='a' * 64, camp_at_collection=camp,
                                        source_data={'public_metrics': {'like_count': 12, 'retweet_count': 3, 'reply_count': 5, 'quote_count': 0}})
    return SpinDiagnosis.objects.create(post=post, status='approved', verdict=verdict, intensity=intensity, headline='H', summary='S.',
                                        analysis='A.', diagnosed_at=timezone.now(), usage={'loaded_words': [{'word': 'okrada', 'kind': 'emotional'}]},
                                        techniques=[{'name': 'Wróg', 'quote': 'Rząd okrada Polaków każdego dnia', 'explanation': 'x'}])


def budget():
    state = ImportState.objects.filter(name='political-x-budget').first()
    return state.cursor if state else {}


# --- flaga i model ---
def test_flag_off_means_no_calls(monkeypatch):
    monkeypatch.setenv('X_REPLIES_ENABLED', 'false')
    x = FakeX(monkeypatch)
    asked = model(monkeypatch)
    diagnosis()
    assert od.run()['status'] == 'disabled'
    assert x.calls == [] and asked == [] and not ReceptionCheck.objects.exists() and budget() == {}


def test_default_is_off(monkeypatch):
    monkeypatch.delenv('X_REPLIES_ENABLED')
    assert od.options()['enabled'] is False
    from news import agent_registry
    assert agent_registry.enabled(agent_registry.REGISTRY['odbior-spinu']) is False


def test_x_not_configured_means_no_calls(monkeypatch):
    monkeypatch.setenv('X_POLITICAL_POLLING_ENABLED', 'false')
    x = FakeX(monkeypatch)
    model(monkeypatch)
    diagnosis()
    assert od.run()['reason'] == 'x_not_configured' and x.calls == []


def test_no_free_model_means_nothing_bought(monkeypatch):
    x = FakeX(monkeypatch)
    monkeypatch.setattr(od, 'model_ready', lambda: False)
    d = diagnosis()
    result = od.run()
    assert result['status'] == 'waiting' and x.calls == [] and budget().get('replies_reads', 0) == 0
    assert od.due() == [d]  # czeka na następny przebieg


# --- budżet ---
def test_reads_settled_to_returned_posts(monkeypatch):
    FakeX(monkeypatch)
    model(monkeypatch)
    diagnosis()
    od.run()
    row = ReceptionCheck.objects.get()
    assert row.reads_used == 1 + len(PRIVATE) and row.cost_usd == Decimal('0.005') * (1 + len(PRIVATE))
    assert budget()['replies_reads'] == 1 + len(PRIVATE)
    assert Decimal(budget()['spent_upper_usd']) == Decimal('0.005') * (1 + len(PRIVATE))


def test_daily_cap_stops_before_request(monkeypatch):
    monkeypatch.setenv('X_REPLIES_DAILY_CAP', '40')
    monkeypatch.setenv('X_REPLIES_PER_POST', '30')
    x = FakeX(monkeypatch)
    model(monkeypatch)
    diagnosis(hours=30)
    diagnosis(hours=28)
    result = od.run()
    # pierwszy: rezerwacja 31, zużyte 12; drugi: 12 + 31 > 40 -> pominięty bez zapytania
    assert result['done'] == 1 and result['skipped:daily_cap'] == 1
    assert x.calls == ['metrics', 'replies'] and budget()['replies_reads'] == 12


def test_low_monthly_budget_is_left_for_collection(monkeypatch):
    x = FakeX(monkeypatch)
    model(monkeypatch)
    now = timezone.now()
    from datetime import timezone as dt_timezone
    ImportState.objects.create(name='political-x-budget', cursor={'month': now.astimezone(dt_timezone.utc).strftime('%Y-%m'),
                                                                   'spent_upper_usd': '40'})
    diagnosis()
    assert od.run()['status'] == 'waiting' and x.calls == []  # 50 - 40 - 0.155 < 25% z 50


def test_blocked_x_skips(monkeypatch):
    x = FakeX(monkeypatch)
    model(monkeypatch)
    ImportState.objects.create(name='political-x-budget', cursor={'blocked_until': (timezone.now() + timedelta(hours=1)).isoformat()})
    diagnosis()
    od.run()
    assert x.calls == []


def test_http_error_refunds_and_retries(monkeypatch):
    x = FakeX(monkeypatch, replies_error=PoliticalReadError('x_http_503', 503))
    model(monkeypatch)
    d = diagnosis()
    od.run()
    row = ReceptionCheck.objects.get()
    assert row.status == 'retry' and row.reads_used == 1 and budget()['replies_reads'] == 1
    assert od.due() == [d]
    assert x.calls == ['metrics', 'replies']


def test_deleted_post_costs_nothing(monkeypatch):
    FakeX(monkeypatch, metrics_error=PoliticalReadError('x_http_404', 404))
    model(monkeypatch)
    diagnosis()
    od.run()
    row = ReceptionCheck.objects.get()
    assert row.status == 'unavailable' and row.reads_used == 0 and budget()['replies_reads'] == 0


# --- RODO i agregacja ---
def test_no_private_data_stored(monkeypatch):
    politician = figure('Anna Publiczna')
    acc = account(politician, 'anna_pub', '777777', camp='opposition')
    FakeX(monkeypatch, extra=[(acc.user_id, '1800000000000000099', 'Pan minister znowu myli fakty')])
    model(monkeypatch)
    diagnosis()
    od.run()
    row = ReceptionCheck.objects.get()
    stored = json.dumps({f.name: str(getattr(row, f.name)) for f in ReceptionCheck._meta.fields}, ensure_ascii=False)
    for author, reply_id, text in PRIVATE:
        assert author not in stored and reply_id not in stored
        assert text[:25] not in stored
    assert 'jan_kowalski' not in stored and 't.co' not in stored
    assert 'marek' not in stored.lower() and 'radomia' not in stored.lower()
    # osoba publiczna z rejestru: nazwa i odnośnik
    assert row.figures == [{'name': 'Anna Publiczna', 'handle': 'anna_pub', 'url': 'https://x.com/anna_pub/status/1800000000000000099'}]


def test_aggregates(monkeypatch):
    FakeX(monkeypatch)
    model(monkeypatch)
    d = diagnosis()
    od.run()
    row = ReceptionCheck.objects.get()
    assert row.status == 'done' and row.sample == 11 and row.model_name == 'groq/test'
    assert row.shares['zgoda'] == round(100 * 7 / 11) and row.shares['sprzeciw'] == round(100 * 3 / 11) and row.shares['kpina'] == round(100 / 11)
    assert row.shares['powtarza'] == round(100 * 3 / 11)  # „rząd okrada Polaków” / „okrada”
    assert row.shares['zrodla'] == round(100 / 11)
    assert row.verdict == 'podchwycony'
    texts = [p['text'] for p in row.phrases]
    assert 'rząd okrada' in texts and 'okrada polaków' not in texts and 'koniec z drożyzną' in texts
    assert all(p['count'] >= 3 for p in row.phrases) and len(row.phrases) <= 3
    data = od.public_data(d)
    assert data['verdict'] == {'key': 'podchwycony', 'label': 'Spin podchwycony'}
    assert data['metrics'][0] == {'key': 'like_count', 'label': 'Polubienia', 'before': 12, 'after': 1450}
    assert 'Próbka 11 odpowiedzi' in data['note'] and 'bez danych osób prywatnych' in data['note']
    from news.clinic import detail_data
    assert detail_data(d)['reception']['sample'] == 11


def test_phrases_drop_names_handles_and_rare():
    texts = ['@ktos Tusk kłamie jak zawsze', 'Wiadomo, Tusk kłamie jak zawsze', 'No i Tusk kłamie jak zawsze', 'jak zawsze to samo',
             'dwa razy coś', 'dwa razy coś']
    out = [p['text'] for p in od.phrases(texts)]
    assert all('tusk' not in p and 'ktos' not in p for p in out)
    assert 'kłamie jak zawsze' in out and 'dwa razy coś' not in out


def test_verdict_thresholds():
    assert od.verdict({'zgoda': 50, 'sprzeciw': 20, 'kpina': 10}, 30) == 'podchwycony'
    assert od.verdict({'zgoda': 20, 'sprzeciw': 25, 'kpina': 15}, 30) == 'odrzucony'
    assert od.verdict({'zgoda': 40, 'sprzeciw': 20, 'kpina': 10}, 30) == 'podzielony'
    assert od.verdict({'zgoda': 90, 'sprzeciw': 0, 'kpina': 0}, 9) == 'za_malo'


def test_model_failure_after_read_keeps_counts_without_rebuying(monkeypatch):
    x = FakeX(monkeypatch)
    model(monkeypatch, fail=True)
    d = diagnosis()
    od.run()
    row = ReceptionCheck.objects.get()
    assert row.status == 'no_model' and row.verdict == '' and row.metrics_after['like_count'] == 1450
    assert od.due() == [] and x.calls == ['metrics', 'replies']
    assert od.public_data(d)['verdict'] is None


# --- ta sama miara ---
def test_same_measure_for_every_camp(monkeypatch):
    FakeX(monkeypatch)
    model(monkeypatch)
    gov = diagnosis(camp='government', hours=30)
    opp = diagnosis(camp='opposition', hours=29)
    diagnosis(camp='opposition', intensity=40)            # za słaby spin - pomijamy w każdym obozie
    diagnosis(camp='government', hours=10)                # jeszcze przed dobą
    diagnosis(camp='government', verdict='no_spin')
    assert od.due() == [gov, opp]
    od.run()
    a, b = ReceptionCheck.objects.get(diagnosis=gov), ReceptionCheck.objects.get(diagnosis=opp)
    assert (a.shares, a.sentiment, a.verdict, a.phrases) == (b.shares, b.sentiment, b.verdict, b.phrases)


# --- raport i rejestr ---
def test_report_contract_and_cost_line(monkeypatch):
    FakeX(monkeypatch)
    model(monkeypatch)
    diagnosis()
    od.run()
    from news import raport_petli
    from news.daily_schedule import BEAT_PLAN
    assert raport_petli.BY_KEY['odbior-spinu']['counter'] == 'reception' and 'odbior-spinu-1h' in BEAT_PLAN
    line = od.report_line()
    assert '12 odczytów X (0.06 USD' in line
    monkeypatch.setenv('X_REPLIES_ENABLED', 'false')
    assert '45.00 USD/30 dni' in od.report_line()
    from news.duty import daily_costs
    assert daily_costs(timezone.now())['replies'] == pytest.approx(0.06)
