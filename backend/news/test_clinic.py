from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from news import clinic, clinic_ai
from news.clinic_models import ClinicDailyMessage, SpinDiagnosis, XAccountSuggestion
from news.political_models import PoliticalAccount, PoliticalPost, PublicFigure

POST_TEXT = 'Rząd podniósł podatki o 50 procent. Tylko my obronimy Polaków!'


def account(camp='opposition', handle='posel_test', user_id='101'):
    return PoliticalAccount.objects.create(user_id=user_id, handle=handle, display_name='Poseł Test', camp=camp, enabled=True)


def post(acc, post_id='9001', text=POST_TEXT, hours_ago=1):
    return PoliticalPost.objects.create(account=acc, post_id=post_id, url=f'https://x.com/{acc.handle}/status/{post_id}',
                                        text=text, published_at=timezone.now() - timedelta(hours=hours_ago),
                                        camp_at_collection=acc.camp)


def fake_diagnosis(verdict='spin', intensity=70):
    return {'verdict': verdict, 'intensity': intensity, 'headline': 'Liczba bez punktu odniesienia',
            'summary': 'Krótko.', 'analysis': 'Dłużej.', 'limitations': '',
            'techniques': [{'name': 'fałszywa alternatywa', 'quote': 'Tylko my obronimy Polaków!', 'explanation': '…'}],
            'claims': [], 'usage': {'model': 'claude-opus-5'}}


@pytest.fixture
def ai_on(monkeypatch):
    monkeypatch.setenv('CLINIC_AI_ENABLED', 'true')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key')
    monkeypatch.setattr(clinic_ai, 'triage', lambda text: None)
    monkeypatch.setattr(clinic_ai, 'diagnose', lambda context: fake_diagnosis())
    monkeypatch.setattr(clinic, 'send_review_alert', lambda: 'queued_only')


def staff():
    return get_user_model().objects.create_user('ordynator', password='x', is_staff=True)


@pytest.mark.django_db
def test_new_post_waits_for_review_and_is_published_only_after_approval(ai_on):
    post(account())
    result = clinic.run_diagnoses(limit=5)
    assert result['created'] == {'pending_review': 1}
    diagnosis = SpinDiagnosis.objects.get()
    client = APIClient()
    assert client.get('/api/clinic/').json()['columns']['opposition'] == []

    client.force_authenticate(staff())
    response = client.post(f'/api/staff/clinic/diagnoses/{diagnosis.pk}/review/', {'decision': 'approve'}, format='json')
    assert response.status_code == 200
    page = APIClient().get('/api/clinic/').json()
    assert [card['id'] for card in page['columns']['opposition']] == [diagnosis.pk]
    assert page['spin_of_day']['id'] == diagnosis.pk
    assert client.post(f'/api/staff/clinic/diagnoses/{diagnosis.pk}/review/', {'decision': 'reject'}, format='json').status_code == 409


@pytest.mark.django_db
def test_review_accepts_only_a_decision_and_only_from_staff(ai_on):
    post(account())
    clinic.run_diagnoses()
    diagnosis = SpinDiagnosis.objects.get()
    client = APIClient()
    assert client.post(f'/api/staff/clinic/diagnoses/{diagnosis.pk}/review/', {'decision': 'approve'}, format='json').status_code in (401, 403)
    client.force_authenticate(staff())
    assert client.post(f'/api/staff/clinic/diagnoses/{diagnosis.pk}/review/', {'decision': 'edit', 'headline': 'x'}, format='json').status_code == 400
    diagnosis.refresh_from_db()
    assert diagnosis.status == 'pending_review' and diagnosis.headline == 'Liczba bez punktu odniesienia'


@pytest.mark.django_db
def test_triage_skips_posts_without_content_to_assess(ai_on, monkeypatch):
    monkeypatch.setattr(clinic_ai, 'triage', lambda text: {'analyze': False, 'reason': 'życzenia', 'model': 'groq'})
    post(account(), text='Wesołych Świąt!')
    clinic.run_diagnoses()
    assert SpinDiagnosis.objects.get().status == 'not_applicable'


@pytest.mark.django_db
def test_disabled_without_key(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    post(account())
    assert clinic.run_diagnoses() == {'status': 'disabled'}
    assert not SpinDiagnosis.objects.exists()


def test_cleaning_drops_invented_quotes_and_unsourced_fact_checks():
    data = {
        'verdict': 'spin', 'intensity': 250, 'headline': 'h', 'summary': 's', 'analysis': 'a', 'limitations': '',
        'techniques': [{'name': 'ok', 'quote': 'tylko  my obronimy polaków!', 'explanation': ''},
                       {'name': 'zmyślony', 'quote': 'czego nie ma w poście', 'explanation': ''}],
        'claims': [{'claim': 'podatki +50%', 'assessment': 'contradicted', 'explanation': '',
                    'sources': [{'url': 'https://example.org/zmyslone', 'title': 'x'}]},
                   {'claim': 'podatki +50%', 'assessment': 'contradicted', 'explanation': '',
                    'sources': [{'url': 'https://stat.gov.pl/dane', 'title': 'GUS'}]}],
    }
    result = clinic_ai.clean_diagnosis(data, POST_TEXT, {'https://stat.gov.pl/dane': 'GUS'})
    assert [t['name'] for t in result['techniques']] == ['ok']
    assert result['claims'][0]['assessment'] == 'unverified' and result['claims'][0]['sources'] == []
    assert result['claims'][1]['assessment'] == 'contradicted'
    assert result['intensity'] == 100 and result['verdict'] == 'spin'


def test_json_is_read_from_the_last_text_block():
    blocks = [SimpleNamespace(type='text', text='Szukam źródeł…'), SimpleNamespace(type='web_search_tool_result'),
              SimpleNamespace(type='text', text='```json\n{"message": "ok", "themes": []}\n```')]
    assert clinic_ai._json_from_text(blocks) == {'message': 'ok', 'themes': []}


@pytest.mark.django_db
def test_reaction_is_required_and_comment_is_optional(ai_on):
    post(account())
    clinic.run_diagnoses()
    diagnosis = SpinDiagnosis.objects.get()
    clinic.review(diagnosis, staff(), 'approve')
    url = f'/api/clinic/spins/{diagnosis.pk}/opinions/'
    client = APIClient()
    assert client.post(url, {'polarity': 'positive'}, format='json').status_code in (401, 403)
    reader = get_user_model().objects.create_user('czytelnik', password='x')
    client.force_authenticate(reader)
    assert client.post(url, {'body': 'sam komentarz'}, format='json').status_code == 400
    assert client.post(url, {'polarity': 'negative', 'body': 'Liczba jest z oficjalnego komunikatu.'}, format='json').status_code == 201
    assert client.post(url, {'polarity': 'positive'}, format='json').status_code == 409
    data = APIClient().get(url).json()
    assert data['counts'] == {'positive': 0, 'negative': 1}
    assert [row['body'] for row in data['negative']] == ['Liczba jest z oficjalnego komunikatu.']


@pytest.mark.django_db
def test_scale_compares_shares_not_counts():
    reviewer = staff()
    gov, opp = account('government', 'min_a', '201'), account('opposition', 'pos_b', '202')
    verdicts = {'government': ['spin'] * 2 + ['no_spin'] * 8, 'opposition': ['spin'] * 10 + ['partial'] * 10 + ['no_spin'] * 20}
    number = 0
    for acc, camp in ((gov, 'government'), (opp, 'opposition')):
        for verdict in verdicts[camp]:
            number += 1
            SpinDiagnosis.objects.create(post=post(acc, str(5000 + number)), verdict=verdict, status='approved',
                                         reviewed_by=reviewer)
    scale = clinic.scale_data(7)
    assert scale['government']['share'] == 0.2
    assert scale['opposition']['share'] == 0.375
    assert scale['enough_data'] is True


@pytest.mark.django_db
def test_hidden_diagnosis_disappears_but_keeps_its_text(ai_on):
    post(account())
    clinic.run_diagnoses()
    diagnosis = SpinDiagnosis.objects.get()
    clinic.review(diagnosis, staff(), 'approve')
    client = APIClient()
    client.force_authenticate(get_user_model().objects.get(username='ordynator'))
    assert client.post(f'/api/staff/clinic/diagnoses/{diagnosis.pk}/hide/', {'reason': 'wniosek prawny'}, format='json').status_code == 200
    assert APIClient().get(f'/api/clinic/spins/{diagnosis.pk}/').status_code == 404
    diagnosis.refresh_from_db()
    assert diagnosis.headline == 'Liczba bez punktu odniesienia'


@pytest.mark.django_db
def test_daily_message_needs_three_posts_and_review(monkeypatch):
    monkeypatch.setenv('CLINIC_AI_ENABLED', 'true')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key')
    monkeypatch.setattr(clinic, 'send_review_alert', lambda: 'queued_only')
    monkeypatch.setattr(clinic_ai, 'daily_message', lambda label, day, posts: {'message': f'{len(posts)} postów', 'themes': ['podatki'], 'usage': {}})
    acc = account('government', 'min_c', '301')
    now = timezone.localtime()
    for number in range(3):
        PoliticalPost.objects.create(account=acc, post_id=str(700 + number), url='https://x.com/min_c/status/1', text='t',
                                     published_at=now.replace(hour=12, minute=number), camp_at_collection='government')
    clinic.run_daily_messages(now.date())
    message = ClinicDailyMessage.objects.get()
    assert message.status == 'pending_review' and message.message == '3 postów'
    assert clinic.daily_message_data('government') is None
    clinic.review(message, staff(), 'approve')
    assert clinic.daily_message_data('government')['themes'] == ['podatki']


@pytest.mark.django_db
def test_x_account_suggestion_from_a_profile_link():
    figure = PublicFigure.objects.create(canonical_name='Anna Test', role_category='parliamentary', role_title='Posłanka',
                                         evidence_url='https://www.sejm.gov.pl')
    client = APIClient()
    url = f'/api/public-figures/{figure.pk}/x-suggestions/'
    assert client.post(url, {'url': 'https://x.com/search?q=anna'}, format='json').status_code == 400
    assert client.post(url, {'url': 'https://twitter.com/Anna_Test'}, format='json').status_code == 201
    assert client.post(url, {'url': 'https://x.com/Anna_Test/'}, format='json').json()['status'] == 'already_suggested'
    assert XAccountSuggestion.objects.get().url == 'https://x.com/Anna_Test'
    listed = client.get('/api/public-figures/?q=Anna').json()['results'][0]
    assert listed['has_x_account'] is False
