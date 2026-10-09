"""Zlecenie 103: korekta jest zamknięta na nowe fakty, modele zawsze zastąpione."""
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from news import thread_review as reviews
from news.account_models import PersonalContextThread
from news.clinic_ai import ClinicAIError
from news.test_thread_signals_091 import accepted
from news.thread_review_models import ThreadReview

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv('THREAD_REVIEW_GATE', 'before')
    monkeypatch.setattr('news.clinic_council.ask', lambda *a, **kw: pytest.fail('Żywy model'))


def row(title='Diagnoza: temat kompromitacja', description='', camps=('government',)):
    thread = PersonalContextThread.objects.create(title=title, description=description,
        signal_kind='lobbying', signal_key=uuid4().hex)
    payload = {'texts': {'title': title, 'description': description},
        'limits': {'title': 65, 'description': 170}, 'boxes': [{}, {}, {}],
        'evidence': {'posts': [{'camp_at_collection': camp, 'text': 'temat'} for camp in camps]}}
    return ThreadReview.objects.create(thread=thread, payload=payload,
        working_texts=deepcopy(payload['texts']), fingerprint='test')


def failure(kind='minor_unsupported', quote='kompromitacja', **checks):
    return {**{key: True for key in reviews.CHECKS}, 'sentence_support': False,
        **checks, 'reason': 'title: fragment bez poparcia.',
        'issues': [{'kind': kind, 'field': 'title', 'quote': quote}]}, 'mock:reviewer'


def install(monkeypatch, reviewer=None, correction=None):
    calls = []
    def ask(role, data):
        calls.append((role, deepcopy(data)))
        if role == reviews.CORRECTION_STEP:
            if correction:
                return correction(data)
            return {'texts': {**data['texts'], 'title': 'Diagnoza: temat'}, 'reason': 'Usunięto ocenę.'}, 'mock:correction'
        if role in (1, 5) and reviewer:
            return reviewer(role, data)
        return accepted(role, data)
    monkeypatch.setattr(reviews, 'ask', ask)
    return calls


def test_minor_word_removed_and_full_review_repeated(monkeypatch):
    review = row()
    original = deepcopy(review.payload)
    calls = install(monkeypatch, lambda role, data: failure() if 'kompromitacja' in data['texts']['title'] else accepted(role, data))
    assert reviews.review_one(review.pk) == 'approved'
    review.refresh_from_db()
    assert review.working_texts['title'] == 'Diagnoza: temat'
    assert review.payload == original
    assert [role for role, _ in calls] == [1, 6, 1, 2, 3, 5]
    assert list(review.rounds.values_list('role', flat=True))[-6:] == list(reviews.ROLES)
    assert review.rounds.filter(role=reviews.CORRECTION_ROLE, result='pass').count() == 1


@pytest.mark.parametrize('kind', ['contradiction', 'unsupported_title', 'meaning_change', 'unequal_treatment'])
def test_fatal_issue_is_not_corrected(monkeypatch, kind):
    review = row()
    calls = install(monkeypatch, lambda role, data: failure(kind))
    assert reviews.review_one(review.pk) == 'rejected'
    assert [role for role, _ in calls] == [1]


def test_wrong_signatory_rejected(monkeypatch):
    review = row('Diagnoza: Tusk podpisał ustawę')
    review.payload['evidence']['source'] = 'Ustawę podpisał prezydent. Tusk jej nie podpisał.'
    review.save()
    calls = install(monkeypatch, lambda role, data: failure('contradiction', 'Tusk podpisał ustawę'))
    assert reviews.review_one(review.pk) == 'rejected'
    assert len(calls) == 1


@pytest.mark.parametrize('camps,expected', [(('government',), 'approved'),
    (('opposition',), 'approved'), (('government', 'opposition'), 'rejected')])
def test_equal_measure_scope(monkeypatch, camps, expected):
    review = row('Diagnoza: temat', camps=camps)
    def reviewer(role, data):
        assert data['comparative'] == (len(camps) == 2)
        answer, model = accepted(role, data)
        answer['equal_measure'] = False
        return answer, model
    install(monkeypatch, reviewer)
    assert reviews.review_one(review.pk) == expected
    if expected == 'approved':
        assert 'nie dotyczy' in review.rounds.last().reason


@pytest.mark.parametrize('suffix,exempt', [('', True), (' Dodatkowe twierdzenie.', False)])
def test_exact_system_description(monkeypatch, suffix, exempt):
    template = next(iter(reviews.SYSTEM_TEMPLATES))
    review = row('Diagnoza: temat', template + suffix)
    def reviewer(role, data):
        assert ('description' in data['system_template_fields']) == exempt
        answer, model = accepted(role, data)
        answer['sentence_support'] = not data['texts']['description']
        return answer, model
    install(monkeypatch, reviewer)
    assert reviews.review_one(review.pk) == ('approved' if exempt else 'rejected')
    review.refresh_from_db()
    assert review.working_texts['description'].replace('\u00a0', ' ') == template + suffix


def test_two_corrections_maximum(monkeypatch):
    review = row('Diagnoza: temat kompromitacja pomyłki nowość')
    def reviewer(role, data):
        return failure(quote=data['texts']['title'].split()[-1])
    def correction(data):
        return {'texts': {**data['texts'], 'title': data['texts']['title'].rsplit(' ', 1)[0]}, 'reason': 'Usunięto fragment.'}, 'mock:correction'
    calls = install(monkeypatch, reviewer, correction)
    assert reviews.review_one(review.pk) == 'rejected'
    assert sum(role == 6 for role, _ in calls) == 2
    assert review.rounds.filter(role=reviews.CORRECTION_ROLE).count() == 2


@pytest.mark.parametrize('title', ['Diagnoza: temat Kowalski', 'Diagnoza: temat 123', 'Diagnoza: nowy temat'])
def test_correction_cannot_add_names_numbers_or_words(monkeypatch, title):
    review = row()
    # Even a word/name/number in evidence cannot be added by correction.
    review.payload['evidence']['extra'] = 'Kowalski 123 nowy'
    review.save()
    install(monkeypatch, lambda role, data: failure(), lambda data: (
        {'texts': {**data['texts'], 'title': title}, 'reason': 'Korekta.'}, 'mock:correction'))
    assert reviews.review_one(review.pk) == 'rejected'
    review.refresh_from_db()
    assert review.working_texts == review.payload['texts']


@pytest.mark.parametrize('error', [ClinicAIError('quota'), ValueError('format')])
def test_wait_resumes_correction_without_losing_budget(monkeypatch, error):
    review = row()
    def broken(data):
        raise error
    install(monkeypatch, lambda role, data: failure(), broken)
    now = timezone.now()
    assert reviews.review_one(review.pk, now=now) == 'waiting'
    review.refresh_from_db()
    assert review.step == reviews.CORRECTION_STEP
    calls = install(monkeypatch)
    assert reviews.review_one(review.pk, now=now + timedelta(hours=2)) == 'approved'
    assert calls[0][0] == reviews.CORRECTION_STEP
    assert review.rounds.filter(role=reviews.CORRECTION_ROLE, result='pass').count() == 1


def test_changed_meaning_after_correction_rejected(monkeypatch):
    review = row()
    def reviewer(role, data):
        if 'kompromitacja' in data['texts']['title']:
            return failure()
        assert 'kompromitacja' in data['original']['title']
        return failure('meaning_change', 'temat', same_meaning=False)
    calls = install(monkeypatch, reviewer)
    assert reviews.review_one(review.pk) == 'rejected'
    assert sum(role == 6 for role, _ in calls) == 1


def test_comparative_uses_metadata_only():
    assert reviews.is_comparative({'evidence': {'posts': [{'camp': 'government'}]},
        'boxes': [{'camp_at_collection': 'opposition'}]})
    assert not reviews.is_comparative({'evidence': {'text': 'government opposition'},
        'texts': {'camp': 'government'}, 'boxes': [{'camp': 'opposition'}]})
    assert not reviews.is_comparative({'evidence': [{'camp': 'government', 'camp_at_collection': 'opposition'}]})


def test_correction_cannot_change_other_fields_or_reorder():
    review = row()
    issues = [{'field': 'title'}]
    original = review.working_texts
    for edited in [{**original, 'description': 'temat'},
                   {**original, 'title': 'temat Diagnoza: kompromitacja'}, original]:
        assert reviews.correction_errors(edited, original, review.payload, issues)


def test_correction_uses_free_linguist_chain(monkeypatch):
    captured = []
    monkeypatch.setattr(reviews, 'free_role', lambda *args: captured.append(args))
    reviews.ask(reviews.CORRECTION_STEP, {'texts': {'title': 'temat'}})
    assert captured[0][0] == 'THREAD_LINGUIST'
    assert captured[0][1] == reviews.CORRECTION


@pytest.mark.parametrize('issues', [{}, '', 'usterka', [{'kind': 'unknown'}]])
def test_malformed_issues_wait(monkeypatch, issues):
    review = row()
    def reviewer(role, data):
        answer, model = accepted(role, data)
        return {**answer, 'issues': issues}, model
    install(monkeypatch, reviewer)
    assert reviews.review_one(review.pk) == 'waiting'


def test_revision_has_own_correction_budget(monkeypatch):
    review = row()
    for _ in range(2):
        review.rounds.create(revision=1, role=reviews.CORRECTION_ROLE,
            result='pass', reason='Starsza rewizja.', texts={})
    review.revision = 2
    review.save()
    install(monkeypatch, lambda role, data: failure() if 'kompromitacja' in data['texts']['title'] else accepted(role, data))
    assert reviews.review_one(review.pk) == 'approved'
    assert review.rounds.filter(revision=2, role=reviews.CORRECTION_ROLE).count() == 1


def test_malformed_correction_waits(monkeypatch):
    review = row()
    install(monkeypatch, lambda role, data: failure(), lambda data: (
        {'texts': None, 'reason': 'Błędny format.'}, 'mock:correction'))
    assert reviews.review_one(review.pk) == 'waiting'
    review.refresh_from_db()
    assert review.step == reviews.CORRECTION_STEP
    assert review.working_texts == review.payload['texts']
