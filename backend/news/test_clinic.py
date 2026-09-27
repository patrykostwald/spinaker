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


def at_hour(monkeypatch, hour, minute=0):
    """Ustala porę dnia dla Kliniki (diagnozy tylko w dzień, tempo zależy od godziny)."""
    moment = timezone.localtime().replace(hour=hour, minute=minute, second=0, microsecond=0)
    monkeypatch.setattr(clinic, 'local_now', lambda: moment)
    return moment


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
    monkeypatch.setenv('CLINIC_AUTO_PUBLISH', 'false')
    monkeypatch.setattr(clinic_ai, 'screen', lambda text: {'score': 90, 'reason': 'konkretne twierdzenie', 'provider': 'groq', 'model': 'm'})
    monkeypatch.setattr(clinic_ai, 'diagnose', lambda context: fake_diagnosis())
    monkeypatch.setattr(clinic, 'send_review_alert', lambda: 'queued_only')
    monkeypatch.setattr(clinic_ai, 'x_thread', x_thread_unavailable)
    at_hour(monkeypatch, 12)


def x_thread_unavailable(diagnosis):
    raise clinic_ai.ClinicAIError('free_models_unavailable')


ORIGINAL_X_THREAD = clinic_ai.x_thread


def pipeline():
    clinic.run_screening()
    return clinic.run_diagnoses()


def staff():
    return get_user_model().objects.create_user('ordynator', password='x', is_staff=True)


@pytest.mark.django_db
def test_new_post_waits_for_review_and_is_published_only_after_approval(ai_on):
    post(account())
    result = pipeline()
    assert result['diagnosed'] == {'pending_review': 1}
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
    pipeline()
    diagnosis = SpinDiagnosis.objects.get()
    client = APIClient()
    assert client.post(f'/api/staff/clinic/diagnoses/{diagnosis.pk}/review/', {'decision': 'approve'}, format='json').status_code in (401, 403)
    client.force_authenticate(staff())
    assert client.post(f'/api/staff/clinic/diagnoses/{diagnosis.pk}/review/', {'decision': 'edit', 'headline': 'x'}, format='json').status_code == 400
    diagnosis.refresh_from_db()
    assert diagnosis.status == 'pending_review' and diagnosis.headline == 'Liczba bez punktu odniesienia'


@pytest.mark.django_db
def test_watcher_skips_low_scores_for_free(ai_on, monkeypatch):
    monkeypatch.setattr(clinic_ai, 'screen', lambda text: {'score': 10, 'reason': 'życzenia', 'provider': 'groq', 'model': 'm'})
    called = []
    monkeypatch.setattr(clinic_ai, 'diagnose', lambda context: called.append(1) or fake_diagnosis())
    post(account(), text='Wesołych Świąt!')
    pipeline()
    assert SpinDiagnosis.objects.get().status == 'not_applicable' and not called


@pytest.mark.django_db
def test_medium_score_waits_for_investigate_decision(ai_on, monkeypatch):
    monkeypatch.setattr(clinic_ai, 'screen', lambda text: {'score': 55, 'reason': 'teza bez liczb', 'provider': 'groq', 'model': 'm'})
    post(account())
    pipeline()
    row = SpinDiagnosis.objects.get()
    assert row.status == 'flagged' and row.screen_score == 55
    client = APIClient()
    client.force_authenticate(staff())
    queue = client.get('/api/staff/clinic/queue/').json()
    assert [item['id'] for item in queue['flagged']] == [row.pk] and queue['flagged'][0]['reason'] == 'teza bez liczb'
    assert client.post(f'/api/staff/clinic/diagnoses/{row.pk}/flag/', {'decision': 'investigate'}, format='json').status_code == 200
    clinic.run_diagnoses()
    row.refresh_from_db()
    assert row.status == 'pending_review' and row.diagnosed_at is not None


@pytest.mark.django_db
def test_dismissed_flag_is_never_paid_for(ai_on, monkeypatch):
    monkeypatch.setattr(clinic_ai, 'screen', lambda text: {'score': 50, 'reason': 'r', 'provider': 'groq', 'model': 'm'})
    post(account())
    clinic.run_screening()
    row = SpinDiagnosis.objects.get()
    client = APIClient()
    client.force_authenticate(staff())
    assert client.post(f'/api/staff/clinic/diagnoses/{row.pk}/flag/', {'decision': 'dismiss'}, format='json').status_code == 200
    clinic.run_diagnoses()
    row.refresh_from_db()
    assert row.status == 'not_applicable' and row.diagnosed_at is None


@pytest.mark.django_db
def test_no_watcher_means_manual_decision_not_blind_spending(ai_on, monkeypatch):
    monkeypatch.setattr(clinic_ai, 'screen', lambda text: None)
    post(account())
    pipeline()
    assert SpinDiagnosis.objects.get().status == 'flagged'


def test_screen_falls_back_to_nim_when_groq_fails(monkeypatch):
    import requests as http
    monkeypatch.setenv('GROQ_API_KEY', 'g')
    monkeypatch.setenv('GROQ_EDITORIAL_MODEL', 'openai/gpt-oss-20b')
    monkeypatch.setenv('NIM_API_KEY', 'n')
    calls = []

    class Reply:
        def __init__(self, status, content=''):
            self.status_code, self.content = status, content
        def raise_for_status(self):
            if self.status_code >= 400:
                raise http.HTTPError(str(self.status_code))
        def json(self):
            return {'choices': [{'message': {'content': self.content}}]}

    def fake_post(url, **kwargs):
        calls.append(url)
        if 'groq' in url:
            return Reply(429)
        return Reply(200, 'Oto ocena: {"score": 83, "reason": "zarzut z liczbami"}')

    monkeypatch.setattr(clinic_ai.requests, 'post', fake_post)
    result = clinic_ai.screen('Rząd podniósł podatki o 50 procent.')
    assert result == {'score': 83, 'reason': 'zarzut z liczbami', 'provider': 'nim', 'model': 'deepseek-ai/deepseek-v4.1-flash'}
    assert 'groq' in calls[0] and 'nvidia' in calls[1]


@pytest.mark.django_db
def test_disabled_without_key(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    monkeypatch.setattr(clinic_ai, 'screen', lambda text: {'score': 90, 'reason': 'r', 'provider': 'groq', 'model': 'm'})
    post(account())
    clinic.run_screening()
    assert clinic.run_diagnoses() == {'status': 'disabled'}
    assert SpinDiagnosis.objects.get().status == 'queued'


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
    pipeline()
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
    pipeline()
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
    monkeypatch.setenv('CLINIC_AUTO_PUBLISH', 'false')
    monkeypatch.setattr(clinic_ai, 'daily_message', lambda label, day, posts: {'message': f'{len(posts)} postów', 'themes': ['podatki'], 'usage': {}})
    now = timezone.localtime()
    for number in range(3):
        acc = account('government', f'min_{number}', str(301 + number))
        PoliticalPost.objects.create(account=acc, post_id=str(700 + number), url='https://x.com/min_c/status/1', text='t',
                                     published_at=now.replace(hour=12, minute=number), camp_at_collection='government')
    one = account('opposition', 'solo', '399')
    for number in range(5):
        PoliticalPost.objects.create(account=one, post_id=str(800 + number), url='https://x.com/solo/status/1', text='t',
                                     published_at=now.replace(hour=12, minute=number), camp_at_collection='opposition')
    clinic.run_daily_messages(now.date())
    assert not ClinicDailyMessage.objects.filter(camp='opposition').exists()  # jedno konto to za mało
    message = ClinicDailyMessage.objects.get(camp='government')
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


@pytest.mark.django_db
def test_auto_mode_publishes_and_fills_the_daily_quota_from_flagged(monkeypatch):
    monkeypatch.setenv('CLINIC_AI_ENABLED', 'true')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key')
    monkeypatch.setenv('CLINIC_AUTO_PUBLISH', 'true')
    monkeypatch.setattr(clinic, 'send_review_alert', lambda: 'queued_only')
    at_hour(monkeypatch, 12)
    monkeypatch.setattr(clinic_ai, 'screen', lambda text: {'score': 55, 'reason': 'teza', 'provider': 'groq', 'model': 'm'})
    monkeypatch.setattr(clinic_ai, 'diagnose', lambda context: fake_diagnosis())
    post(account())
    clinic.run_screening()
    assert SpinDiagnosis.objects.get().status == 'flagged'
    clinic.run_diagnoses()
    row = SpinDiagnosis.objects.get()
    assert row.status == 'approved' and row.reviewed_by_id is None
    assert APIClient().get(f'/api/clinic/spins/{row.pk}/').json()['auto_published'] is True


@pytest.mark.django_db
def test_failures_do_not_use_the_daily_quota_but_a_series_of_them_stops_spending(ai_on, monkeypatch):
    def broken(context):
        raise clinic_ai.ClinicAIError('api_404: model not found')
    monkeypatch.setattr(clinic_ai, 'diagnose', broken)
    monkeypatch.setenv('CLINIC_DAILY_FAILURE_LIMIT', '2')
    acc = account()
    for index in range(4):
        post(acc, post_id=str(9100 + index))
    clinic.run_screening()
    clinic.run_diagnoses(limit=2)
    assert clinic.failures_today() == 2 and clinic.diagnoses_today() == 0
    assert SpinDiagnosis.objects.filter(status='failed').first().error.startswith('api_404: model not found')
    assert clinic.run_diagnoses(limit=2) == {'status': 'too_many_failures', 'failed_today': 2}
    assert SpinDiagnosis.objects.filter(status='queued').count() == 2


@pytest.mark.django_db
def test_no_diagnoses_at_night_and_the_quota_is_spread_over_the_day(ai_on, monkeypatch):
    acc = account()
    for index in range(10):
        post(acc, post_id=str(9200 + index))
    clinic.run_screening()
    at_hour(monkeypatch, 3)
    assert clinic.run_diagnoses() == {'status': 'night'}
    at_hour(monkeypatch, 8)
    clinic.run_diagnoses()
    clinic.run_diagnoses()
    # O 8:00 minęła 1/16 dnia: z 19 zwykłych diagnoz należą się 2 — nie cały limit naraz.
    assert clinic.diagnoses_today() == 2


@pytest.mark.django_db
def test_evening_slot_goes_to_the_most_popular_post_and_it_becomes_spin_of_the_day(ai_on, monkeypatch):
    monkeypatch.setenv('CLINIC_AUTO_PUBLISH', 'true')
    small, big = account(handle='maly', user_id='201'), account(handle='duzy', user_id='202', camp='government')
    quiet = post(small, post_id='9301', hours_ago=2)
    loud = post(big, post_id='9302', hours_ago=2)
    PoliticalPost.objects.filter(pk=loud.pk).update(author_data={'public_metrics': {'followers_count': 900000}},
                                                    source_data={'public_metrics': {'like_count': 500}})
    PoliticalPost.objects.filter(pk=quiet.pk).update(author_data={'public_metrics': {'followers_count': 800}})
    monkeypatch.setattr(clinic_ai, 'screen', lambda text: {'score': 50, 'reason': 'r', 'provider': 'groq', 'model': 'm'})
    clinic.run_screening()
    evening = at_hour(monkeypatch, 18, 5)
    # Posty z tego samego dnia co „teraz” testu — niezależnie od godziny uruchomienia (też tuż po północy).
    PoliticalPost.objects.update(published_at=evening - timedelta(hours=2))
    monkeypatch.setattr(clinic_ai, 'diagnose', lambda context: fake_diagnosis(intensity=30))
    clinic.run_diagnoses(limit=0)
    featured = clinic.featured_today()
    assert featured.post_id == loud.pk and featured.status == 'approved'
    assert clinic.spin_of_day()['id'] == featured.pk


@pytest.mark.django_db
def test_only_fresh_posts_are_diagnosed(ai_on):
    acc = account()
    old = post(acc, post_id='9401', hours_ago=40)
    new = post(acc, post_id='9402', hours_ago=2)
    clinic.run_screening()
    clinic.run_diagnoses()
    assert SpinDiagnosis.objects.get(post=new).status == 'pending_review'
    assert SpinDiagnosis.objects.get(post=old).status == 'queued'


def test_daily_message_input_fits_the_free_model_limit():
    posts = [{'author': f'Poseł {i % 30}', 'text': 'Bardzo długi wpis o podatkach. ' * 40} for i in range(60)]
    text = clinic_ai._daily_input('opozycja', '2026-09-26', posts)
    assert len(text) <= clinic_ai.DAILY_INPUT_CHARS
    assert 'Poseł 29' in text  # każdy autor trafia do wejścia, zanim ktokolwiek dostanie drugi wpis


def test_daily_message_in_english_is_retried_and_then_rejected(monkeypatch):
    answers = iter([({'message': 'Opposition stresses high fuel prices and the budget deficit.', 'themes': ['Fuel prices']}, 'm'),
                    ({'message': 'Opozycja podkreśla wysokie ceny paliw i deficyt budżetowy.', 'themes': ['ceny paliw']}, 'm')])
    monkeypatch.setattr(clinic_ai, '_free_chat', lambda *args, **kwargs: next(answers))
    result = clinic_ai.daily_message('opozycja', '2026-09-26', [{'author': 'A', 'text': 'x'}])
    assert result['message'].startswith('Opozycja')
    monkeypatch.setattr(clinic_ai, '_free_chat', lambda *args, **kwargs: ({'message': 'Only English here.', 'themes': []}, 'm'))
    with pytest.raises(clinic_ai.ClinicAIError):
        clinic_ai.daily_message('opozycja', '2026-09-26', [{'author': 'A', 'text': 'x'}])


@pytest.mark.django_db
def test_interview_pipeline_keeps_only_quotes_from_the_transcript(monkeypatch):
    from news import clinic_interview
    from news.clinic_models import ClinicInterview
    monkeypatch.setattr(clinic_interview, '_oembed', lambda url: {'title': 'Kropka nad i', 'author_name': 'TVN24', 'thumbnail_url': 'https://i.ytimg.com/x.jpg'})
    monkeypatch.setattr(clinic_interview, 'transcribe', lambda url: ({'guest_name': 'Jan Kowalski', 'host_name': 'Anna Nowak', 'segments': [
        {'time': '01:05', 'speaker': 'guest', 'text': 'Podatki spadły o połowę, to nasz sukces.'},
        {'time': '02:10', 'speaker': 'host', 'text': 'Ale dane GUS mówią co innego.'}]
        + [{'time': f'1{i}:00', 'speaker': who, 'text': 'Dalsza część rozmowy o budżecie.'} for i in range(6) for who in ('host', 'guest')]},
        {'model': 'gemini'}))

    def fake_call(system, user, schema, **kwargs):
        return SimpleNamespace(content=[], stop_reason='end_turn', usage=None, model='claude-opus-5')
    monkeypatch.setattr(clinic_ai, '_call', fake_call)
    monkeypatch.setattr(clinic_ai, '_json_from_text', lambda blocks: {
        'headline': 'H', 'summary': 'S', 'overall': 'O', 'limitations': '',
        'guest': {'verdict': 'spin', 'intensity': 70, 'summary': 'g', 'claims': [],
                  'techniques': [{'name': 'wybiórczość', 'quote': 'Podatki spadły o połowę', 'time': '01:05', 'explanation': 'e'},
                                 {'name': 'zmyślony', 'quote': 'Tego nie powiedział', 'time': '03:00', 'explanation': 'e'}]},
        'host': {'verdict': 'no_spin', 'intensity': 150, 'summary': 'h',
                 'notes': [{'name': 'dopytanie', 'quote': 'dane GUS mówią co innego', 'time': '02:10', 'explanation': 'e'}]}})
    interview = clinic_interview.process(clinic_interview.queue_interview('https://youtu.be/abcdefghijk'))
    assert interview.status == 'approved' and interview.title == 'Kropka nad i'
    assert [t['quote'] for t in interview.guest_analysis['techniques']] == ['Podatki spadły o połowę']
    assert interview.guest_analysis['techniques'][0]['seconds'] == 65
    data = clinic.clinic_page_data()
    assert data['interview']['host']['notes'][0]['time'] == '02:10'
    # Prowadzący ma werdykt w tej samej skali co gość; siła przycięta do 0–100.
    assert data['interview']['host']['verdict'] == 'no_spin' and data['interview']['host']['intensity'] == 100
    assert data['interview']['host']['verdict_label'] == 'Bez spinu'
    assert ClinicInterview.objects.count() == 1
    with pytest.raises(ValueError):
        clinic_interview.queue_interview('https://example.com/video')


@pytest.mark.django_db
def test_spin_of_day_is_the_strongest_today_and_latest_is_the_newest(ai_on, monkeypatch):
    monkeypatch.setenv('CLINIC_AUTO_PUBLISH', 'true')
    acc = account()
    strong, newer = post(acc, post_id='9501', hours_ago=3), post(acc, post_id='9502', hours_ago=1)
    # Oba posty z „dzisiaj” w czasie testu (12:00) — wynik nie zależy od godziny uruchomienia.
    noon = clinic.local_now()
    PoliticalPost.objects.filter(pk=strong.pk).update(published_at=noon - timedelta(hours=3))
    PoliticalPost.objects.filter(pk=newer.pk).update(published_at=noon - timedelta(hours=1))
    clinic.run_screening()
    intensities = iter([90, 40])
    monkeypatch.setattr(clinic_ai, 'diagnose', lambda context: fake_diagnosis(intensity=next(intensities)))
    for row in SpinDiagnosis.objects.order_by('post__published_at'):
        clinic.diagnose(row)
    assert clinic.spin_of_day()['intensity'] == 90
    assert clinic.latest_spin()['post']['id'] == newer.post_id



@pytest.mark.django_db
def test_loudest_political_interview_of_yesterday_is_picked(monkeypatch):
    from news import clinic_interview
    monkeypatch.setenv('CLINIC_INTERVIEW_ENABLED', 'true')
    monkeypatch.setenv('GEMINI_API_KEY', 'g')
    monkeypatch.setenv('CLINIC_AI_ENABLED', 'true')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'k')
    monkeypatch.setenv('CLINIC_INTERVIEW_CHANNELS', '@kanal')
    videos = {
        'aaaaaaaaaaa': ('Wywiad: premier Tusk o budżecie', 'PT45M', 90000),        # najważniejszy polityk: 90k × 3
        'bbbbbbbbbbb': ('Rozmowa z posłem Nowakiem', 'PT30M', 100000),             # mniej znany i za cichy — odpada
        'ccccccccccc': ('Zapowiedź: Tusk w rozmowie już dziś', 'PT1M', 900000),    # zapowiedź — za krótka
        'ddddddddddd': ('Żurek broni Wałęsy — komentarz Mazurka', 'PT20M', 500000),  # klasyfikator: monolog
    }

    searches = []

    def fake_yt(path, **params):
        if path == 'channels' and 'forHandle' in params:
            return {'items': [{'id': 'UC1'}]}
        if path == 'channels':  # liczby subskrypcji kanałów spoza listy
            return {'items': [{'id': 'UCbig', 'statistics': {'subscriberCount': '900000'}},
                              {'id': 'UCsmall', 'statistics': {'subscriberCount': '800'}}]}
        if path == 'search':  # dwa zapytania po całym YouTube — nie więcej (osobny, mały limit dzienny)
            searches.append(params['q'])
            return {'items': [
                {'id': {'videoId': 'eeeeeeeeeee'}, 'snippet': {'title': 'Wywiad: Kaczyński o wyborach', 'description': 'rozmowa',
                                                               'channelTitle': 'Duży podcast', 'channelId': 'UCbig'}},
                {'id': {'videoId': 'fffffffffff'}, 'snippet': {'title': 'Wywiad: Tusk PRZERÓBKA', 'description': 'rozmowa',
                                                               'channelTitle': 'Mały kanał', 'channelId': 'UCsmall'}}]}
        if path == 'playlistItems':
            yesterday = (timezone.localtime() - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
            old = yesterday - timedelta(days=3)
            return {'items': [{'contentDetails': {'videoId': vid, 'videoPublishedAt': yesterday.isoformat()},
                               'snippet': {'title': title, 'description': 'rozmowa', 'channelTitle': 'Kanał'}}
                              for vid, (title, _, _) in videos.items()]
                             + [{'contentDetails': {'videoId': 'zzzzzzzzzzz', 'videoPublishedAt': old.isoformat()},
                                 'snippet': {'title': 'Stary wywiad: premier Tusk', 'description': 'rozmowa', 'channelTitle': 'Kanał'}}]}
        catalog = {**videos, 'eeeeeeeeeee': ('Wywiad: Kaczyński o wyborach', 'PT40M', 50000),
                   'fffffffffff': ('Wywiad: Tusk PRZERÓBKA', 'PT40M', 5000000)}
        return {'items': [{'id': vid, 'contentDetails': {'duration': duration}, 'statistics': {'viewCount': str(views)}}
                          for vid, (_, duration, views) in catalog.items() if vid in params['id']]}
    monkeypatch.setattr(clinic_interview, '_yt', fake_yt)
    monkeypatch.setattr(clinic_interview, 'looks_like_interview', lambda title, description, channel: ('Mazurka' not in title, ''))
    result = clinic_interview.pick_yesterday()
    assert result['status'] == 'queued' and 'Tusk' in result['title'] and result['top_politician']
    assert 'PRZERÓBKA' not in result['title'] and len(searches) == 2  # mały kanał spoza listy odpada mimo wyświetleń
    ranked_ids = [row['video_id'] for row in clinic_interview.rank_interviews(timezone.localdate() - timedelta(days=1))]
    assert 'eeeeeeeeeee' in ranked_ids and 'fffffffffff' not in ranked_ids
    assert clinic_interview.pick_yesterday()['status'] == 'already_chosen'


@pytest.mark.django_db
def test_monologue_is_rejected_before_paying_for_the_diagnosis(monkeypatch):
    from news import clinic_interview
    monkeypatch.setattr(clinic_interview, '_oembed', lambda url: {})
    monkeypatch.setattr(clinic_interview, 'transcribe', lambda url: ({'guest_name': 'Lech Wałęsa', 'host_name': 'Robert Mazurek', 'segments':
        [{'time': f'0{i}:00', 'speaker': 'host', 'text': 'Długi komentarz prowadzącego. ' * 20} for i in range(9)]
        + [{'time': '09:30', 'speaker': 'guest', 'text': 'Krótki cytat.'}]}, {'model': 'gemini'}))
    paid = []
    monkeypatch.setattr(clinic_interview, 'diagnose_transcript', lambda meta, transcript: paid.append(1))
    interview = clinic_interview.process(clinic_interview.queue_interview('https://youtu.be/abcdefghijk'))
    assert interview.status == 'not_applicable' and interview.error.startswith('nie_wywiad') and not paid



@pytest.mark.django_db
def test_interview_is_processed_only_once(monkeypatch):
    from news import clinic_interview
    interview = clinic_interview.queue_interview('https://youtu.be/abcdefghijk')
    assert clinic_interview.claim(interview) is True
    assert clinic_interview.claim(interview) is False
    assert clinic_interview.queue_interview('https://youtu.be/abcdefghijk').status == clinic_interview.IN_PROGRESS



@pytest.mark.django_db
def test_x_thread_synthesis_is_saved_once_and_rejects_english(ai_on, monkeypatch):
    post(account())
    pipeline()
    diagnosis = SpinDiagnosis.objects.get()
    assert diagnosis.x_thread == []  # darmowy model niedostępny — diagnoza i tak zapisana
    answers = [{'lead': 'The post blames the government.', 'points': ['One point here.', 'Another point here.']},
               {'lead': 'Wpis przypisuje rządowi intencje bez dowodu.',
                'points': ['Technika: fałszywa alternatywa — „Tylko my obronimy Polaków!”.', 'Twierdzenie o podatkach nie ma źródła w diagnozie.']}]
    monkeypatch.setattr(clinic_ai, '_free_chat', lambda *args, **kwargs: (answers.pop(0), 'm'))
    monkeypatch.setattr(clinic_ai, 'x_thread', ORIGINAL_X_THREAD)
    assert clinic.ensure_x_thread(diagnosis) is True
    diagnosis.refresh_from_db()
    assert diagnosis.x_thread[0] == 'Wpis przypisuje rządowi intencje bez dowodu.' and len(diagnosis.x_thread) == 3
    assert diagnosis.verdict == 'spin' and diagnosis.intensity == 70  # synteza nie zmienia diagnozy
    assert clinic.ensure_x_thread(diagnosis) is False  # tylko raz


def test_silent_classifier_is_not_a_rejection(monkeypatch):
    from news import clinic_interview
    monkeypatch.setattr(clinic_interview, 'CLASSIFY_RETRIES', (0, 0))
    calls = []
    monkeypatch.setattr(clinic_ai, '_free_chat', lambda *a, **k: calls.append(1) or (_ for _ in ()).throw(clinic_ai.ClinicAIError('rate')))
    ok, reason = clinic_interview.looks_like_interview('Błaszczak: Tusk łata dziurę | Gość Dzisiaj', '', 'Republika')
    assert ok is None and len(calls) == 2  # ponowiona próba, potem „nie wiem”, a nie „nie”
    assert clinic_interview.talk_signal('Błaszczak: Tusk łata dziurę | Gość Dzisiaj', '')
    assert not clinic_interview.talk_signal('Dzisiaj Informacje 26.09.2026', 'serwis informacyjny')
    assert clinic_interview.talk_signal('Szydło: Nie mieści mi się w głowie, że służby do tego dopuściły', '')
    # „Major wywiadu” (służby), rozmowa z ekspertem — bez polityka w tytule i bez słowa „wywiad” jako całego wyrazu.
    assert not clinic_interview.talk_signal('Fortu Trump nie będzie. Major wywiadu Robert Cheda i Jan Piński', 'rozmowa')


@pytest.mark.django_db
def test_deleted_posts_keep_the_fact_but_not_the_text(ai_on, monkeypatch):
    from news import deleted_posts
    acc = account()
    kept, gone = post(acc, post_id='9601'), post(acc, post_id='9602')
    status = {kept.url: 200, gone.url: 404}
    monkeypatch.setattr(deleted_posts.requests, 'get', lambda url, params, timeout, headers: SimpleNamespace(status_code=status[params['url']]))
    assert deleted_posts.check_batch(pause=0) == {'checked': 2, 'deleted': 1}
    gone.refresh_from_db(); kept.refresh_from_db()
    assert not gone.available and gone.text == '' and gone.unavailable_at  # zasady X: treść usuniętego wpisu znika
    assert kept.available and kept.availability_checked_at
    data = APIClient().get('/api/clinic/deleted/').json()
    assert len(data['items']) == 1 and data['items'][0]['author']['handle'] == acc.handle and 'text' not in data['items'][0]
    assert data['week_by_camp'] == {'opposition': 1}


@pytest.mark.django_db
def test_weekly_report_collects_the_week_without_paid_models(ai_on, monkeypatch):
    from news import weekly_report
    monkeypatch.setenv('CLINIC_AUTO_PUBLISH', 'true')
    post(account())
    pipeline()
    monkeypatch.setattr(clinic_ai, '_free_chat', lambda *a, **k: ({'summary': 'W tym tygodniu Dr. Spin ocenił jeden post opozycji, w którym użyto fałszywej alternatywy.'}, 'm'))
    report = weekly_report.generate()
    assert report.summary.startswith('W tym tygodniu') and report.data['diagnoses'] == {'government': 0, 'opposition': 1}
    assert report.data['techniques']['opposition'][0]['name'] == 'fałszywa alternatywa'
    data = APIClient().get('/api/clinic/report/').json()
    assert data['report']['week_end'] == str(report.week_end) and data['archive'][0]['week_end'] == str(report.week_end)
    assert APIClient().get('/api/clinic/report/nie-data/').status_code == 404


def test_gemini_diagnosis_keeps_only_sources_found_by_google(monkeypatch):
    import json as _json
    monkeypatch.setenv('CLINIC_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_API_KEY', 'g')
    answer = {'verdict': 'spin', 'intensity': 60, 'headline': 'H', 'summary': 'S', 'analysis': 'A', 'limitations': '',
              'techniques': [{'name': 'fałszywa alternatywa', 'quote': 'Tylko my obronimy Polaków!', 'explanation': 'e'}],
              'claims': [{'claim': 'Podatki wzrosły o 50%', 'assessment': 'contradicted', 'explanation': 'e',
                          'sources': [{'url': 'https://www.gus.gov.pl/inny-adres', 'title': 'GUS'},
                                      {'url': 'https://zmyslone.example/x', 'title': 'X'}]}]}
    payload = {'candidates': [{'content': {'parts': [{'text': '```json\n' + _json.dumps(answer) + '\n```'}]}, 'finishReason': 'STOP',
                               'groundingMetadata': {'webSearchQueries': ['podatki 2026'],
                                                     'groundingChunks': [{'web': {'uri': 'https://redirect.example/abc', 'title': 'gus.gov.pl'}}]}}],
               'usageMetadata': {'promptTokenCount': 1000, 'candidatesTokenCount': 500}}
    monkeypatch.setattr(clinic_ai.requests, 'post', lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: payload, text=''))
    monkeypatch.setattr(clinic_ai.requests, 'head', lambda *a, **k: SimpleNamespace(headers={'Location': 'https://gus.gov.pl/dane'}))
    result = clinic_ai.diagnose({'author': 'A', 'camp_label': 'Opozycja', 'published_at': '2026-09-27', 'url': 'u', 'text': POST_TEXT})
    sources = [s['url'] for s in result['claims'][0]['sources']]
    assert sources == ['https://gus.gov.pl/dane']  # ta sama domena → adres z wyników; zmyślona strona odpada
    assert result['usage']['model'].startswith('gemini') and 0 < clinic_ai.cost_usd(result['usage']) < 0.1
