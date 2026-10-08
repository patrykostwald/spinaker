from io import StringIO
from unittest.mock import Mock
from uuid import uuid4

import pytest
from django.core.management import call_command, CommandError
from django.utils import timezone

from news import thread_review as reviews
from news.account_models import PersonalContextThread
from news.management.commands.requeue_rejected_threads import eligible_reason
from news.test_thread_signals_091 import accepted
from news.thread_review_models import ThreadReview


def payload(text='Diagnoza: temat', evidence='', boxes=None):
    return {'texts': {'title': text, 'description': ''},
            'limits': {'title': 65, 'description': 170},
            'evidence': evidence, 'boxes': boxes if boxes is not None else [{}, {}, {}]}


@pytest.mark.parametrize('text,evidence,valid', [
    ('Zajączkowska-Hernik', 'Zajączkowska-Hernik', True),
    ('Zajączkowska-Hernik', 'Zajączkowska', False),
    ('Miłosza', 'Miłosz', True), ('Motyki', 'Motyka', True),
    ('Kowalczykowska', 'Miłosz Motyka', False),
    ('Jan', 'Janusz', False), ('Miłoszowego', 'Miłosz', False),
    ('Diagnoza', '', True), ('Czytaj', '', True),
])
def test_names(text, evidence, valid):
    data = payload(text, evidence)
    assert (reviews.measure(data['texts'], data) == []) == valid


@pytest.mark.parametrize('term', ['kłamstwo', 'na zlecenie', 'lobbował', 'załatwił'])
@pytest.mark.parametrize('source', ['evidence', 'boxes', 'absent'])
def test_accusations(term, source):
    data = payload(f'Wpis: „{term}”')
    if source == 'evidence':
        data['evidence'] = term.upper()
    elif source == 'boxes':
        data['boxes'][0] = {'quote': term.upper()}
    errors = reviews.measure(data['texts'], data)
    assert errors == []  # filtr zarzutów usunięty 9.10


@pytest.mark.parametrize('text,error', [
    ('właściciel', 'wewnętrzne ustalenia'), ('temat temat', 'powtórzenie wyrazu'),
    ('temat. temat.', 'powtórzone zdanie'), ('a' * 66, 'limit znaków'),
])
def test_other_guards_unchanged(text, error):
    data = payload(text, text)
    assert any(error in item for item in reviews.measure(data['texts'], data))


ACCUSATION = 'title: słowo z listy zarzutów.'
NAME = '0.box.body: nazwa własna spoza danych (Miłosza).'


@pytest.mark.parametrize('reason,valid', [
    (ACCUSATION, True), (NAME, True), (ACCUSATION + '; ' + NAME, True),
    (ACCUSATION + '; title: brak dowodu.', False),
    (NAME + '; title: limit znaków lub pusty tytuł.', False),
    ('brak dowodu: ' + ACCUSATION, False), ('', False), (ACCUSATION + ';', False),
])
def test_reason_whitelist(reason, valid):
    assert eligible_reason(reason) == valid


def row(reason=ACCUSATION, status='rejected'):
    thread = PersonalContextThread.objects.create(title='Diagnoza: temat', is_public=False,
        signal_kind='lobbying', signal_key=uuid4().hex)
    data = payload()
    return ThreadReview.objects.create(thread=thread, reason=reason, status=status, step=4,
        next_attempt_at=timezone.now(), payload=data, working_texts=data['texts'], fingerprint='test')


@pytest.mark.django_db
def test_plan_apply_limit_and_no_publication(monkeypatch):
    publish = Mock(side_effect=AssertionError('Komenda nie publikuje'))
    monkeypatch.setattr(reviews, '_apply', publish)
    selected = row()
    second = row(NAME)
    mixed = row(ACCUSATION + '; title: brak dowodu.')
    pending = row(status='pending')
    for args in [(), ('--plan',)]:
        out = StringIO()
        call_command('requeue_rejected_threads', *args, stdout=out)
        selected.refresh_from_db()
        assert selected.status == 'rejected' and selected.step == 4
        assert 'kwalifikujące: 2; wybrane: 2; wznowione: 0' in out.getvalue()
    call_command('requeue_rejected_threads', '--apply', limit=0, stdout=StringIO())
    selected.refresh_from_db()
    assert selected.status == 'rejected'
    call_command('requeue_rejected_threads', '--apply', limit=1, stdout=StringIO())
    selected.refresh_from_db()
    assert (selected.status, selected.step, selected.reason, selected.next_attempt_at) == ('pending', 0, '', None)
    assert selected.working_texts == selected.payload['texts'] and selected.revision == 1
    for untouched in [second, mixed, pending]:
        untouched.refresh_from_db()
        assert untouched.step == 4 and untouched.reason
    selected.thread.refresh_from_db()
    assert not selected.thread.is_public
    publish.assert_not_called()
    with pytest.raises(CommandError):
        call_command('requeue_rejected_threads', limit=-1)


@pytest.mark.django_db
def test_default_limit():
    for _ in range(21):
        row()
    call_command('requeue_rejected_threads', '--apply', stdout=StringIO())
    assert ThreadReview.objects.filter(status='pending').count() == 20
    assert ThreadReview.objects.filter(status='rejected').count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize('reject_step', [None, 1, 5])
def test_full_review_after_requeue(monkeypatch, reject_step):
    review = row()
    def answer(role, data):
        result, model = accepted(role, data)
        if role == reject_step:
            result.update(sentence_support=False, no_overreach=False, reason='Brak dowodu przypisania zarzutu.')
        return result, model
    ask = Mock(side_effect=answer)
    monkeypatch.setattr(reviews, 'ask', ask)
    assert reviews.review_one(review.pk) == 'rejected'
    ask.assert_not_called()
    call_command('requeue_rejected_threads', '--apply', stdout=StringIO())
    review.thread.refresh_from_db()
    assert not review.thread.is_public
    assert reviews.run_queue() == {review.pk: 'approved' if reject_step is None else 'rejected'}
    review.refresh_from_db()
    expected = reviews.ROLES if reject_step is None else reviews.ROLES[:reject_step + 1]
    assert list(review.rounds.values_list('role', flat=True)) == list(expected)
    review.thread.refresh_from_db()
    assert review.thread.is_public == (reject_step is None)
