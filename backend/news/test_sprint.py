from datetime import datetime, timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from rest_framework.test import APIClient

from news import sprint
from news.agent_models import AgentNote, BuildTicket

pytestmark = pytest.mark.django_db
MONDAY = timezone.make_aware(datetime(2026, 10, 12, 6, 0))
TUESDAY = MONDAY + timedelta(days=1)


@pytest.fixture(autouse=True)
def no_seba(monkeypatch):
    monkeypatch.setenv('SEBA_ENABLED', 'false')


def idea(title, agent='architekt', status='new', score=85, kind='idea', days=1, **scores):
    return AgentNote.objects.create(agent=agent, kind=kind, title=title, body='opis', status=status, score=score,
                                    scores=scores, created_at=MONDAY - timedelta(days=days))


def test_candidates_rank_dedupe_and_filters():
    idea('Oś czasu wypowiedzi posła', score=90, effort='S', value=9, brief='Zbuduj oś', acceptance=['działa'])
    idea('Oś czasu wypowiedzi posłów', score=85)  # duplikat (podobieństwo > 0,85)
    idea('Eksport grafu do CSV', status='accepted', score=40, effort='L')  # akceptacja właściciela: +25
    idea('Niska ocena', score=70)
    idea('Naprawa pętli X', agent='opiekun', status='accepted', score=95)
    idea('Pomysł spoza listy', agent='ekspert', score=95)
    banned = idea('Profil prywatnej osoby', score=99)
    AgentNote.objects.create(agent='prawnik', kind='review', title='Ocena', body='', created_at=MONDAY - timedelta(hours=1),
                             scores={'verdicts': [{'note': banned.pk, 'what': 'Pomysł: Profil prywatnej osoby', 'verdict': 'niedozwolone'}]})
    titles = [c['title'] for c in sprint.candidates(MONDAY)]
    assert titles == ['Oś czasu wypowiedzi posła', 'Eksport grafu do CSV']
    assert sprint.similar('przeszłość.today: Oś czasu wypowiedzi posła', 'Oś czasu wypowiedzi posłów')


def test_rank_formula_and_conditional_legal():
    assert sprint.rank(90, 9, 'S', False, 0, '') == 36 + 27
    assert sprint.rank(40, 4, 'L', True, 30, 'warunkowo') == 16 + 25 + 4 + 8 - 30


def test_wynalazca_findings_expand_to_items():
    idea('Nowe pomysły: 2', agent='wynalazca', kind='finding', score=0,
         ideas=[{'title': 'Mapa powiązań spółek', 'wow': 9, 'tier': 'Pro', 'what': 'graf'}, {'title': 'Słabe', 'wow': 3}])
    [cand] = sprint.candidates(MONDAY)
    assert cand['title'] == 'Mapa powiązań spółek' and cand['effort'] == 'L' and 'graf' in cand['brief']


def test_intake_weekly_cap_expiry_and_daily_topup(django_user_model):
    for n in range(10):
        idea(f'Zupełnie inny pomysł numer {n} o {"abcdefghij"[n] * 6}', score=80 + n)
    old = BuildTicket.objects.create(title='Stara propozycja', created_at=MONDAY - timedelta(days=8))
    result = sprint.intake(MONDAY)
    assert result['mode'] == 'tydzień' and result['expired'] == 1 and len(result['created']) == 8
    old.refresh_from_db()
    assert old.status == 'dropped' and old.decided_by is None
    assert sprint.intake(TUESDAY)['mode'] == 'pełna kolejka'
    owner = django_user_model.objects.create_user(username='owner', is_staff=True)
    BuildTicket.objects.filter(status='proposed').update(status='dropped', decided_by=owner, decided_at=TUESDAY)
    assert len(sprint.intake(TUESDAY)['created']) == 2  # dopełnienie z pozostałych kandydatów
    ticket = BuildTicket.objects.filter(status='proposed').first()
    assert ticket.due_date == TUESDAY.date() + timedelta(days=7)


def test_decision_api(django_user_model):
    source = idea('Oś czasu', effort='S')
    ticket = BuildTicket.objects.create(note=source, title='Oś czasu', effort='S')
    client = APIClient()
    url = f'/api/staff/sprint/{ticket.pk}/decision/'
    assert client.get('/api/staff/sprint/').status_code in (401, 403)
    client.force_authenticate(django_user_model.objects.create_user(username='reader'))
    assert client.post(url, {'decision': 'approved'}).status_code == 403
    staff = django_user_model.objects.create_user(username='staff', is_staff=True)
    client.force_authenticate(staff)
    assert client.post(url, {'decision': 'zrób'}).status_code == 400
    response = client.post(url, {'decision': 'approved'})
    assert response.status_code == 200 and response.data['status'] == 'approved'
    assert response.data['due_date'] == (timezone.localdate() + timedelta(days=3)).isoformat()
    assert client.post(url, {'decision': 'approved'}).status_code == 409
    listing = client.get('/api/staff/sprint/').data
    assert listing['open'] == 1 and listing['results'][0]['agent'] == 'architekt'
    assert client.post(url, {'decision': 'dropped'}).status_code == 200
    ticket.refresh_from_db()
    assert ticket.status == 'dropped' and ticket.decided_by == staff
    # „Nie teraz” właściciela: pomysł nie wraca od razu
    assert sprint.candidates() == []


def test_command_prints_briefs_and_closes_ticket():
    source = idea('Eksport CSV', effort='M', brief='Dodaj eksport', acceptance=['plik się pobiera'])
    ticket = BuildTicket.objects.create(note=source, title='Eksport CSV', brief='Dodaj eksport', acceptance=['plik się pobiera'],
                                        status='approved', due_date=MONDAY.date())
    out = StringIO()
    call_command('sprint_zlecenia', stdout=out)
    text = out.getvalue()
    assert f'Zlecenie #{ticket.pk}' in text and 'Cel: Eksport CSV' in text and '- plik się pobiera' in text
    with pytest.raises(CommandError):
        call_command('sprint_zlecenia', zrobione=ticket.pk, stdout=StringIO())
    call_command('sprint_zlecenia', zrobione=ticket.pk, commit='abc1234', stdout=StringIO())
    ticket.refresh_from_db()
    source.refresh_from_db()
    assert ticket.status == 'done' and ticket.commit == 'abc1234' and ticket.done_at
    assert source.status == 'done'
    assert sprint.candidates() == []


def test_close_multi_idea_finding_marks_built_items():
    items = [{'title': 'Mapa spółek', 'wow': 9}, {'title': 'Eksport do CSV', 'wow': 9}]
    note = idea('Nowe pomysły', agent='wynalazca', kind='finding', ideas=items)
    sprint.close(BuildTicket.objects.create(note=note, title='Mapa spółek', status='approved'), 'aaa')
    note.refresh_from_db()
    assert note.status == 'new' and note.scores['zbudowane'] == ['Mapa spółek']
    assert [c['title'] for c in sprint.candidates()] == ['Eksport do CSV']
    sprint.close(BuildTicket.objects.create(note=note, title='Eksport do CSV', status='approved'), 'bbb')
    note.refresh_from_db()
    assert note.status == 'done'


def test_sprint_intake_command_is_data_free():
    out = StringIO()
    call_command('sprint_intake', stdout=out)
    assert 'Nowe bilety: 0' in out.getvalue()
    idea('Oś czasu', score=95)
    out = StringIO()
    call_command('sprint_intake', podglad=True, stdout=out)
    assert 'Oś czasu' in out.getvalue() and not BuildTicket.objects.exists()
