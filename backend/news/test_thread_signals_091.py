"""Offline regression suite: every network/model boundary is blocked or mocked."""
from copy import deepcopy
from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.utils import timezone

from news import signal_threads as signals, thread_review as reviews
from news.account_models import PersonalContextThread
from news.clinic_ai import ClinicAIError
from news.community import public_threads
from news.thread_review_models import ThreadReview

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def offline(monkeypatch, settings):
    settings.THREADS_ENABLED = True
    def forbidden(*args, **kwargs):
        pytest.fail('Test attempted real HTTP/AI')
    monkeypatch.setattr('requests.sessions.Session.request', forbidden)
    monkeypatch.setattr('news.clinic_council.ask', forbidden)
    monkeypatch.setattr('news.clinic_ai._free_chat', forbidden)
    monkeypatch.setenv('THREADS_ENABLED', 'true')


TEXT = ('W art. 5 dodaje się przepis określający zasady przekazywania informacji o jakości produktu '
        'oraz obowiązek przedstawienia szczegółowego wykazu składników na opakowaniu sprzedawanego towaru.')


def records():
    return [{'id': str(i), 'term': 10, 'print': '123', 'kind': 'amendment', 'text': TEXT,
             'url': f'https://api.sejm.gov.pl/sejm/term10/prints/123/plik{i}.pdf', 'author': club,
             'clubs': [club], 'label': f'Poprawka {i}'} for i, club in enumerate(['Klub A', 'Klub B'], 1)]


def draft():
    signals.build_lobbying(records())
    return PersonalContextThread.objects.get(signal_kind='lobbying')


def accepted(role, data):
    if role == 2:
        return {'texts': dict(data['texts']), 'reason': 'Poprawiono język bez zmiany sensu.'}, 'mock:linguist'
    return {**{k: True for k in reviews.CHECKS}, 'reason': 'Każde zdanie ma pokrycie w danych.'}, 'mock:reviewer'


def test_confidence_rules_and_symmetry():
    assert signals.confidence('twins', .71) == 'niski'
    assert signals.confidence('twins', .72) == 'średni'
    assert signals.confidence('consultation', .949) == 'średni'
    assert signals.confidence('twins', .95) == 'wysoki'
    assert signals.confidence('twins', 1, True) == 'niski'
    rows = records()
    signal = signals.lobbying_signals(rows)[0]
    assert signal['confidence'] == 'wysoki' and signal['connection'] == 'Ten sam zapis.'
    assert signals.lobbying_signals(list(reversed(rows)))[0]['score'] == signal['score']
    rows[1]['clubs'] = rows[0]['clubs']
    assert not signals.lobbying_signals(rows)


def test_technical_low_does_not_create_thread():
    rows = records()
    for row in rows:
        row['text'] = 'Ustawa wchodzi w życie po upływie 14 dni. ' + TEXT
    assert signals.lobbying_signals(rows)[0]['confidence'] == 'niski'
    assert signals.build_lobbying(rows) == []
    assert not PersonalContextThread.objects.exists()


def test_consultation_and_explicit_registry():
    rows = records()
    rows[1].update(kind='consultation', author='Izba Testowa')
    assert 'zgłoszone w konsultacjach przez: Izba Testowa' in signals.lobbying_signals(rows)[0]['connection']
    registry = {**rows[1], 'kind': 'registry', 'confirmed': True}
    assert signals.lobbying_signals([registry])[0]['confidence'] == 'wysoki'
    assert not signals.lobbying_signals([{**registry, 'print': ''}])
    assert not signals.lobbying_signals([{**registry, 'confirmed': False}])
    assert not signals.lobbying_signals([{**registry, 'term': None}])
    assert len(signals.build_lobbying([registry])) == 1


def test_other_print_term_and_partial_prefix_are_not_twins():
    for field, value in [('print', '124'), ('term', 9), ('url', 'javascript:alert(1)')]:
        rows = records()
        rows[1][field] = value
        assert not signals.lobbying_signals(rows)
    assert signals.similarity(TEXT + ' ' + 'X' * 2000, TEXT + ' ' + 'Y' * 2000) < .72


def test_pilot_parser_and_negative_declarations():
    from news.lobbying_rules import amendments, declarations
    body = f'1) {TEXT}\n- KP Klub A\n- przyjąć\n2) {TEXT}\n- KP Klub B\n- odrzucić'
    assert [r['clubs'] for r in amendments(body)] == [['Klub A'], ['Klub B']]
    positive = 'Izba Testowa zgłosiła zainteresowanie pracami nad projektem ustawy.'
    assert declarations(positive)[0]['author'] == 'Izba Testowa'
    assert not declarations(positive.replace('zgłosiła', 'nie zgłosiła'))
    assert not declarations('Projekt udostępniono zgodnie z ustawą o działalności lobbingowej.')


def phrase_rows(now, phrase='bezpieczny koszyk lokalnych inwestycji', camps=None):
    return [{'id': i, 'text': phrase + '.', 'author_id': str(i), 'account_id': i, 'author': f'Autor {i}',
             'camp': (camps or ['government'] * 3)[i], 'reach': i * 10, 'url': f'https://example.org/{i}',
             'published_at': now - timedelta(hours=3-i)} for i in range(3)]


def test_phrase_window_baseline_future_and_distinct_authors():
    now = timezone.now()
    rows = phrase_rows(now)
    assert signals.find_new_phrases(rows, now)[0]['authors'] == 3
    old = {**rows[0], 'id': 8, 'published_at': now-timedelta(hours=48, seconds=1)}
    assert not signals.find_new_phrases(rows + [old], now)
    assert not signals.find_new_phrases(rows + [{**old, 'published_at': now-timedelta(days=16)}], now)
    assert signals.find_new_phrases(rows + [{**old, 'published_at': now-timedelta(days=16, seconds=1)}], now)
    assert signals.find_new_phrases(rows + [{**old, 'published_at': now+timedelta(seconds=1)}], now)
    rows[2]['author_id'] = rows[1]['author_id']
    assert not signals.find_new_phrases(rows, now)


def test_both_camps_one_chronological_thread_and_longest_phrase():
    now = timezone.now()
    found = signals.find_new_phrases(phrase_rows(now, camps=['government', 'opposition', 'government']), now)
    assert len(found) == 1
    assert found[0]['phrase'] == 'bezpieczny koszyk lokalnych inwestycji'
    boxes = signals.narrative_boxes(found[0])
    assert [b['box_data']['political_post_id'] for b in boxes[:-1]] == [0, 1, 2]
    assert boxes[-1]['box_data']['box_type'] == 'summary'


def test_rank_authors_then_reach():
    now = timezone.now()
    a = phrase_rows(now)
    b = [{**r, 'id': r['id']+10, 'reach': 1000} for r in phrase_rows(now, 'zielony program transportu powiatowego')]
    assert signals.find_new_phrases(a+b, now)[0]['phrase'] == 'zielony program transportu powiatowego'
    a.append({**a[0], 'id': 8, 'author_id': '8', 'account_id': 8})
    assert signals.find_new_phrases(a+b, now)[0]['authors'] == 4


def test_daily_limit_and_repeat_runs(monkeypatch):
    from news.political_models import PoliticalAccount, PoliticalPost
    now = timezone.now()
    for group, phrase in enumerate(['bezpieczny koszyk lokalnych inwestycji', 'zielony program transportu powiatowego', 'wspólna mapa szpitalnych potrzeb']):
        for i in range(3):
            key = str(group*10+i+1)
            account = PoliticalAccount.objects.create(user_id=key, handle='fixture'+key, display_name='Autor '+key, camp='government')
            PoliticalPost.objects.create(account=account, post_id=key, url='https://example.org/'+key, text=phrase,
                published_at=now-timedelta(hours=i), camp_at_collection='government', source_data={'public_metrics': {'impression_count': group*100}})
    assert len(signals.build_new_narratives(now)) == 2
    assert signals.build_new_narratives(now) == []
    assert signals.build_new_narratives(now+timedelta(days=1))  # next day, only the unused story
    assert PersonalContextThread.objects.count() == 3
    assert not public_threads().exists()


def test_complete_gate_language_and_two_reviews(monkeypatch):
    thread = draft()
    review = thread.publication_review
    assert not thread.is_public and not public_threads().exists()
    mock = Mock(side_effect=accepted)
    monkeypatch.setattr(reviews, 'ask', mock)
    assert reviews.review_one(review.pk) == 'approved'
    thread.refresh_from_db()
    assert thread.is_public and public_threads().filter(pk=thread.pk).exists()
    review.refresh_from_db()
    assert list(review.rounds.values_list('role', flat=True)) == list(reviews.ROLES)
    assert mock.call_count == 3
    # After the linguist every text is in final typography (short dashes, hard spaces after one-letter words).
    assert all(reviews.typography(v) == v for v in review.working_texts.values())
    assert reviews.typography('Dane z sejmu i opinie \u2014 test') == 'Dane z\u00a0sejmu i\u00a0opinie - test'
    assert reviews.review_one(review.pk) == 'approved' and mock.call_count == 3


@pytest.mark.parametrize('step', [1, 4])
def test_factual_rejection_never_publishes(monkeypatch, step):
    thread = draft()
    def reject(role, data):
        answer, model = accepted(role, data)
        if role == step:
            answer['no_overreach'] = False
            answer['reason'] = 'Wniosek wykracza poza przytoczone dane.'
        return answer, model
    monkeypatch.setattr(reviews, 'ask', reject)
    assert reviews.review_one(thread.publication_review.pk) == 'rejected'
    thread.refresh_from_db()
    assert not thread.is_public and not public_threads().exists()
    assert thread.publication_review.rounds.last().result == 'reject'


def test_language_cannot_change_evidence_and_remeasurement_rejects(monkeypatch):
    thread = draft()
    original = list(thread.items.values_list('box_data', flat=True))
    def too_long(role, data):
        answer, model = accepted(role, data)
        if role == 2:
            answer['texts']['title'] = 'x'*81
        return answer, model
    monkeypatch.setattr(reviews, 'ask', too_long)
    assert reviews.review_one(thread.publication_review.pk) == 'rejected'
    assert thread.publication_review.rounds.last().role == 'Miernik po korekcie'
    assert list(thread.items.values_list('box_data', flat=True))[:3] == original[:3]


def test_quota_wait_resumes_at_unfinished_step(monkeypatch):
    thread = draft()
    def unavailable(role, data):
        if role == 4:
            raise ClinicAIError('quota')
        return accepted(role, data)
    monkeypatch.setattr(reviews, 'ask', unavailable)
    now = timezone.now()
    assert reviews.review_one(thread.publication_review.pk, now=now) == 'waiting'
    thread.refresh_from_db()
    assert not thread.is_public
    review = ThreadReview.objects.get(thread=thread)
    assert review.step == 4 and review.next_attempt_at > now
    mock = Mock(side_effect=accepted)
    monkeypatch.setattr(reviews, 'ask', mock)
    assert reviews.review_one(review.pk, now=now) == 'waiting' and not mock.called
    assert reviews.review_one(review.pk, now=now+timedelta(hours=1, seconds=1)) == 'approved'
    assert mock.call_count == 1 and mock.call_args.args[0] == 4


@pytest.mark.parametrize('text', ['Poseł lobbował.', 'Poseł załatwił sprawę.', 'Działa na zlecenie.', 'Kowalski mówi o projekcie.'])
def test_meter_accusations_and_unknown_surnames(text):
    thread = draft()
    payload = thread.publication_review.payload
    assert reviews.measure({**payload['texts'], 'title': text}, payload)


def test_meter_limits_repetitions_internal_text():
    payload = draft().publication_review.payload
    for text in ['Zapis zapis dotyczy projektu.', 'Konsylium uznało', 'x'*81]:
        assert reviews.measure({**payload['texts'], 'title': text}, payload)


def test_approved_edit_revokes_and_audit_survives(monkeypatch):
    thread = draft()
    monkeypatch.setattr(reviews, 'ask', accepted)
    assert reviews.review_one(thread.publication_review.pk) == 'approved'
    thread.refresh_from_db()
    thread.title = 'Sygnał lobbingu: inny druk'
    thread.save()
    thread.refresh_from_db()
    assert not thread.is_public
    review = ThreadReview.objects.get(thread=thread)
    assert review.revision == 2 and review.step == 0 and review.rounds.count() == 5


def test_generator_is_idempotent_after_review(monkeypatch):
    thread = draft()
    monkeypatch.setattr(reviews, 'ask', accepted)
    assert reviews.review_one(thread.publication_review.pk) == 'approved'
    assert signals.build_lobbying(records()) == [thread.pk]
    thread.refresh_from_db()
    assert thread.is_public and thread.publication_review.revision == 1


def test_direct_publish_does_not_bypass_queue():
    thread = draft()
    thread.is_public = True
    thread.save()
    thread.refresh_from_db()
    assert not thread.is_public


def test_free_only_guard_even_with_paid_configuration(monkeypatch):
    from news import clinic_council as council, council_registry as registry
    monkeypatch.setattr(council, '_members', lambda *args: [('gemini', 'gemini-x'), ('openrouter', 'paid'), ('mistral', 'paid')])
    available = Mock(return_value=True)
    monkeypatch.setattr(registry, 'available', available)
    with pytest.raises(ClinicAIError):
        reviews.free_role('THREAD_REVIEWER', '', {}, {}, 1)
    assert not available.called


def test_no_truncated_evidence_review():
    with pytest.raises(ValueError, match='rozmiar'):
        reviews.ask(1, {'evidence': 'x'*12001})


def test_actual_090_and_official_adapters():
    from news.models import Source, Article, OfficialRecord, ArticleContent
    from news.public_records_models import PublicRecord
    source = Source.objects.create(name='Sejm', url='https://api.sejm.gov.pl')
    article = Article.objects.create(source=source, title='Projekt testowy', url='https://api.sejm.gov.pl/sejm/term10/prints/123', published_date=timezone.now())
    official = OfficialRecord.objects.create(article=article, provider='sejm', external_id='print/10/123', api_url=article.url, raw_data={})
    ArticleContent.objects.create(article=article, source_url=article.url,
        text=f'1) {TEXT}\n- KP Klub A\n- przyjąć\n2) {TEXT}\n- KP Klub B\n- przyjąć')
    PublicRecord.objects.create(source='consultations', kind='consultation', external_id='osr/1', term=10,
        print_number='123', official_print=official, source_url=article.url, title='Izba Testowa', text=TEXT,
        data={'cytat_uwagi': TEXT[:40]})
    parsed = signals.local_lobbying_records()
    assert len(parsed) == 3 and parsed[-1]['text'] == TEXT
    assert len(signals.build_lobbying()) == 3
